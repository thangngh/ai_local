#!/usr/bin/env python3
"""Run full local gate pipeline and write a single summary file."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)

SUMMARY_PATH = ROOT / ".reports" / "pipeline-summary.md"
LOG_PATH = ROOT / ".reports" / "pipeline-run.log"


def run_step(label: str, args: list[str]) -> tuple[bool, str]:
    cmd = [str(PYTHON), "-m", "ai_local.cli", *args]
    completed = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    passed = completed.returncode == 0
    line = f"[{'PASS' if passed else 'FAIL'}] {label} (exit={completed.returncode})\n{output.strip()}\n"
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"\n{'=' * 72}\n==> {label}\n{line}")
    return passed, output.strip()


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_summary(step_results: list[tuple[str, bool, str]]) -> str:
    generated = datetime.now(UTC).isoformat()
    lines = [
        "# Full Pipeline Summary",
        "",
        f"**Generated:** {generated}",
        f"**Python:** `{PYTHON}`",
        "",
        "## Step results",
        "",
        "| Step | Status |",
        "|------|--------|",
    ]
    all_passed = True
    for label, passed, _ in step_results:
        status = "PASS" if passed else "FAIL"
        lines.append(f"| {label} | {status} |")
        if not passed:
            all_passed = False

    lines.extend(["", f"**Overall:** {'PASS' if all_passed else 'FAIL'}", ""])

    doctor_block = next((out for lbl, _, out in step_results if lbl == "doctor"), "")
    if doctor_block:
        lines.extend(["## Doctor", "", "```text", doctor_block, "```", ""])

    gate_report = _load_json(ROOT / ".reports" / "phase-fast-gate" / "latest.json")
    if gate_report:
        lines.extend(
            [
                "## Phase fast gate",
                "",
                f"- passed: {gate_report.get('passed_count')}/{gate_report.get('total')}",
                f"- source: {gate_report.get('source_ref')}",
                "",
            ]
        )
        failed = [r for r in gate_report.get("results", []) if not r.get("passed")]
        if failed:
            lines.append("### Failed gates")
            for item in failed:
                lines.append(f"- {item.get('phase')}.{item.get('id')}: {item.get('summary')}")
            lines.append("")

    benchmark_report = _load_json(ROOT / ".reports" / "benchmark" / "latest.json")
    if benchmark_report:
        agg = benchmark_report.get("aggregate", {})
        cost = benchmark_report.get("cost", {})
        lines.extend(
            [
                "## Benchmark (harness)",
                "",
                f"- run_id: `{benchmark_report.get('run_id')}`",
                f"- mode: {benchmark_report.get('run_mode')}",
                f"- passed: {agg.get('pass_count')}/{agg.get('total')}",
                f"- harness_score: {agg.get('harness_system_score')}",
                f"- blended_score: {agg.get('system_score')}",
                f"- tier: {agg.get('tier')}",
                f"- tokens: {cost.get('total_tokens', 0)}",
                "",
            ]
        )
        partial_or_fail = [
            t
            for t in benchmark_report.get("tasks", [])
            if t.get("result") != "pass"
        ]
        if partial_or_fail:
            lines.append("### Tasks needing review")
            for task in partial_or_fail:
                lines.append(
                    f"- {task.get('task_id')}: {task.get('result')} "
                    f"h={task.get('harness_system_score')} blend={task.get('system_score')}"
                )
            lines.append("")

    summary_md = ROOT / ".reports" / "benchmark"
    if benchmark_report:
        run_id = benchmark_report.get("run_id", "")
        task_summary = summary_md / f"{run_id}_summary.md"
        if task_summary.exists():
            lines.extend(["## Benchmark table", "", task_summary.read_text(encoding="utf-8"), ""])

    history_path = ROOT / ".reports" / "benchmark" / "history.jsonl"
    if history_path.exists():
        entries = [ln for ln in history_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        lines.extend(["## Recent benchmark history", "", f"Entries: {len(entries)} (last 5)", ""])
        for entry_line in entries[-5:]:
            entry = json.loads(entry_line)
            lines.append(
                f"- `{entry.get('run_id')}` mode={entry.get('run_mode')} "
                f"blend={entry.get('blended_score')} harness={entry.get('harness_score')} "
                f"pass={entry.get('pass_count')}/{entry.get('total')}"
            )
        lines.append("")

    lines.extend(
        [
            "## Raw log",
            "",
            f"Full command output: `{LOG_PATH.relative_to(ROOT).as_posix()}`",
            "",
        ]
    )
    for label, passed, output in step_results:
        if not passed and output:
            lines.extend([f"### {label} (failed)", "", "```text", output[:8000], "```", ""])
    return "\n".join(lines)


def main() -> int:
    LOG_PATH.write_text(f"# Pipeline run {datetime.now(UTC).isoformat()}\n", encoding="utf-8")
    steps: list[tuple[str, list[str]]] = [
        ("doctor", ["doctor", "--skip-ollama"]),
        (
            "phase-fast-gate",
            [
                "phase-fast-gate",
                "--clean",
                "--output",
                ".reports/phase-fast-gate/latest.json",
            ],
        ),
        ("promote", ["promote", "--max-level", "hard"]),
        (
            "benchmark-run",
            [
                "benchmark-run",
                "--output",
                ".reports/benchmark/latest.json",
                "--enforce-thresholds",
            ],
        ),
    ]
    results: list[tuple[str, bool, str]] = []
    stop_on_fail = {"doctor", "phase-fast-gate"}
    for label, args in steps:
        passed, output = run_step(label, args)
        results.append((label, passed, output))
        if not passed and label in stop_on_fail:
            break

    if all(passed for _, passed, _ in results):
        passed, output = run_step(
            "benchmark-replay",
            ["benchmark-replay", "--run", ".reports/benchmark/latest.json", "--only-flagged"],
        )
        results.append(("benchmark-replay", passed, output))

    summary = build_summary(results)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(summary, encoding="utf-8")
    print(f"SUMMARY {SUMMARY_PATH}")
    return 0 if all(passed for _, passed, _ in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
