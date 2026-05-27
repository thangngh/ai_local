from __future__ import annotations

import json
from pathlib import Path

from ai_local.benchmark.history import load_benchmark_history
from ai_local.benchmark.replay import load_benchmark_report, render_replay_report
from ai_local.benchmark.regression import (
    compute_regression_baseline,
    enforce_regression_gate,
    load_regression_policy,
)
from ai_local.benchmark.thresholds import enforce_thresholds, load_benchmark_thresholds
def _latest_glob(report_dir: Path, pattern: str) -> Path | None:
    matches = sorted(report_dir.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _read_optional_text(path: Path) -> str | None:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return None


def _sparkline(values: list[float]) -> str:
    if not values:
        return "(no data)"
    blocks = "▁▂▃▄▅▆▇█"
    low = min(values)
    high = max(values)
    if high == low:
        return blocks[-1] * len(values)
    chars: list[str] = []
    for value in values:
        idx = int((value - low) / (high - low) * (len(blocks) - 1))
        chars.append(blocks[idx])
    return "".join(chars)


def write_benchmark_dashboard(
    report_dir: Path = Path(".reports/benchmark"),
    *,
    output: Path | None = None,
    regression_config: Path = Path("configs/benchmark_regression.yaml"),
    thresholds_config: Path = Path("configs/benchmark_thresholds.yaml"),
) -> Path:
    output_path = output or report_dir / "dashboard.md"
    latest_path = report_dir / "latest.json"
    adversarial_path = report_dir / "adversarial_latest.json"
    ollama_path = report_dir / "ollama_latest.json"
    history_path = report_dir / "history.jsonl"

    sections: list[str] = ["# Benchmark dashboard", ""]

    overall_pass = True
    last_run_id = "-"
    last_mode = "-"
    if latest_path.exists():
        report = load_benchmark_report(latest_path)
        last_run_id = report.run_id
        last_mode = report.run_mode
        thresholds = load_benchmark_thresholds(thresholds_config)
        if enforce_thresholds(report, thresholds):
            overall_pass = False
        if report.aggregate.fail_count > 0:
            overall_pass = False
        policy = load_regression_policy(regression_config)
        if enforce_regression_gate(
            report,
            history_path=history_path,
            policy=policy,
            task_pack="golden",
        ):
            overall_pass = False

    sections.append("## 1. Executive")
    sections.append(f"- Overall: **{'PASS' if overall_pass else 'FAIL'}**")
    sections.append(f"- Last run: `{last_run_id}` mode=`{last_mode}`")
    sections.append("")

    sections.append("## 2. Score separation")
    for label, path in (
        ("golden harness", _latest_glob(report_dir, "*_harness_scores.json")),
        ("golden llm", _latest_glob(report_dir, "*_llm_scores.json")),
        ("golden blended", _latest_glob(report_dir, "*_blended_scores.json")),
    ):
        if path is None:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        aggregate = payload.get("aggregate", {})
        sections.append(
            f"- {label}: system={aggregate.get('system_score', aggregate.get('harness_system_score', '-'))}"
        )
    sections.append("")

    if latest_path.exists():
        report = load_benchmark_report(latest_path)
        agg = report.aggregate
        sections.append("## 3. Layer metrics")
        sections.append(
            f"- Memory active_with_evidence: {agg.memory_metrics.active_memory_with_evidence:.3f}"
        )
        sections.append(f"- Retrieval MRR: {agg.retrieval_metrics.mrr:.3f}")
        sections.append(f"- Patch test pass rate: {agg.patch_metrics.test_pass_rate:.3f}")
        sections.append("")

    history = load_benchmark_history(history_path, limit=10)
    sections.append("## 4. Trend (last 10 runs)")
    if history:
        blended = [entry.blended_score for entry in history]
        sections.append(f"- Blended sparkline: `{_sparkline(blended)}`")
        sections.append("")
        sections.append("| run_id | pack | mode | blended | harness | pass |")
        sections.append("| --- | --- | --- | ---: | ---: | --- |")
        for entry in history:
            sections.append(
                f"| {entry.run_id} | {entry.pack} | {entry.run_mode} | "
                f"{entry.blended_score:.3f} | {entry.harness_score:.3f} | "
                f"{entry.pass_count}/{entry.total} |"
            )
    else:
        sections.append("_No history entries._")
    sections.append("")

    compare_md = report_dir / "compare" / "latest_comparison.md"
    if not compare_md.exists():
        compare_md = _latest_glob(report_dir / "compare", "*/comparison.md")
    sections.append("## 5. Model comparison")
    comparison_text = _read_optional_text(compare_md) if compare_md else None
    if comparison_text:
        sections.append(comparison_text)
    else:
        sections.append("_No model comparison artifact._")
    sections.append("")

    if latest_path.exists():
        report = load_benchmark_report(latest_path)
        sections.append("## 6. Flagged tasks")
        sections.append("```")
        sections.append(
            render_replay_report(report, llm_alert_below=0.70, only_flagged=True)
        )
        sections.append("```")
        sections.append("")

    perf_summary = Path(".reports/performance_optimization_summary.md")
    if perf_summary.exists():
        sections.append("## Performance notes")
        sections.append(_read_optional_text(perf_summary) or "")
        sections.append("")

    sections.append("## 7. Raw artifacts")
    for artifact in (
        latest_path,
        adversarial_path,
        ollama_path,
        history_path,
        compare_md,
    ):
        if artifact is not None and artifact.exists():
            sections.append(f"- `{artifact.as_posix()}`")

    if adversarial_path.exists():
        adv_report = load_benchmark_report(adversarial_path)
        policy = load_regression_policy(regression_config)
        baseline = compute_regression_baseline(
            history_path,
            run_mode=adv_report.run_mode,
            task_pack="golden+adversarial",
            exclude_run_id=adv_report.run_id,
            policy=policy,
        )
        sections.append("")
        sections.append("### Adversarial latest")
        sections.append(
            f"- score={adv_report.aggregate.harness_system_score:.3f} "
            f"pass={adv_report.aggregate.pass_count}/{adv_report.aggregate.total}"
        )
        if baseline:
            sections.append(f"- regression baseline runs={baseline['baseline_runs']}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(sections).strip() + "\n", encoding="utf-8")
    return output_path
