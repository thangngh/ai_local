from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ai_local.benchmark.history import load_benchmark_history, render_trend_table
from ai_local.benchmark.replay import load_benchmark_report, render_replay_report
from ai_local.benchmark.regression import compute_regression_baseline, load_regression_policy
from ai_local.benchmark.summary import render_summary_table
from ai_local.benchmark.thresholds import enforce_thresholds, load_benchmark_thresholds
def _load_json_report(path: Path):
    if not path.exists():
        return None
    return load_benchmark_report(path)


def _report_row(label: str, path: Path, report) -> list[str]:
    if report is None:
        return [label, "-", "-", "-", "-", "-", f"missing `{path.as_posix()}`"]
    agg = report.aggregate
    llm = f"{agg.llm_system_score:.4f}" if agg.llm_system_score is not None else "-"
    return [
        label,
        report.run_id,
        report.run_mode,
        f"{agg.pass_count}/{agg.total}",
        f"{agg.harness_system_score:.4f}",
        llm,
        f"{agg.system_score:.4f}",
    ]


def write_overall_summary(
    report_dir: Path = Path(".reports/benchmark"),
    *,
    output: Path | None = None,
    phase_gate_path: Path = Path(".reports/phase-fast-gate/latest.json"),
    pipeline_summary_path: Path = Path(".reports/pipeline-summary.md"),
    thresholds_config: Path = Path("configs/benchmark_thresholds.yaml"),
    regression_config: Path = Path("configs/benchmark_regression.yaml"),
) -> Path:
    output_path = output or report_dir / "overall_summary.md"
    now = datetime.now(UTC).isoformat()

    golden = _load_json_report(report_dir / "latest.json")
    ollama = _load_json_report(report_dir / "ollama_latest.json")
    adversarial = _load_json_report(report_dir / "adversarial_latest.json")

    thresholds = load_benchmark_thresholds(thresholds_config)
    regression_policy = load_regression_policy(regression_config)
    history_path = report_dir / "history.jsonl"

    lines: list[str] = [
        "# Báo cáo tổng thể — Benchmark & Release Gate",
        "",
        f"**Sinh lúc:** {now}",
        "",
        "## 1. Tóm tắt điều hành",
        "",
    ]

    gate_pass = True
    checks: list[tuple[str, str, str]] = []

    if phase_gate_path.exists():
        phase_payload = json.loads(phase_gate_path.read_text(encoding="utf-8"))
        phase_ok = bool(phase_payload.get("passed"))
        phase_count = phase_payload.get("passed_count", "?")
        total_gates = len(phase_payload.get("results", []))
        checks.append(
            (
                "Phase fast gate",
                "PASS" if phase_ok else "FAIL",
                f"{phase_count}/{total_gates} gates",
            )
        )
        if not phase_ok:
            gate_pass = False
    else:
        checks.append(("Phase fast gate", "N/A", "no artifact"))

    for label, report, adversarial_pack in (
        ("Golden harness", golden, False),
        ("Golden + Ollama", ollama, False),
        ("Golden + adversarial", adversarial, True),
    ):
        if report is None:
            checks.append((label, "N/A", "no report"))
            continue
        fail = report.aggregate.fail_count > 0
        th_violations = enforce_thresholds(report, thresholds, adversarial_pack=adversarial_pack)
        reg_violations: list[str] = []
        pack = "golden+adversarial" if adversarial_pack else "golden"
        baseline = compute_regression_baseline(
            history_path,
            run_mode=report.run_mode,
            task_pack=pack,
            exclude_run_id=report.run_id,
            policy=regression_policy,
        )
        if baseline is not None:
            from ai_local.benchmark.regression import enforce_regression_gate

            reg_violations = enforce_regression_gate(
                report,
                history_path=history_path,
                policy=regression_policy,
                task_pack=pack,
            )
        status = "PASS"
        detail = f"{report.aggregate.pass_count}/{report.aggregate.total} tasks"
        if fail or th_violations or reg_violations:
            status = "FAIL"
            gate_pass = False
            parts: list[str] = []
            if fail:
                parts.append(f"fail_count={report.aggregate.fail_count}")
            if th_violations:
                parts.append(f"thresholds={len(th_violations)}")
            if reg_violations:
                parts.append(f"regression={len(reg_violations)}")
            detail = "; ".join(parts)
        checks.append((label, status, detail))

    lines.append(f"**Trạng thái tổng:** {'PASS' if gate_pass else 'FAIL'}")
    lines.append("")
    lines.append("| Thành phần | Trạng thái | Chi tiết |")
    lines.append("| --- | --- | --- |")
    for name, status, detail in checks:
        lines.append(f"| {name} | {status} | {detail} |")
    lines.append("")

    lines.append("## 2. Bảng điểm theo pack")
    lines.append("")
    lines.append("| Pack | run_id | mode | pass | harness | llm | blended |")
    lines.append("| --- | --- | --- | --- | ---: | ---: | ---: |")
    for row in (
        _report_row("Golden (22)", report_dir / "latest.json", golden),
        _report_row("Ollama full", report_dir / "ollama_latest.json", ollama),
        _report_row("Golden+adv (32)", report_dir / "adversarial_latest.json", adversarial),
    ):
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    lines.append("## 3. Chỉ số lớp (golden harness mới nhất)")
    if golden is not None:
        agg = golden.aggregate
        mem = agg.memory_metrics
        ret = agg.retrieval_metrics
        patch = agg.patch_metrics
        lines.extend(
            [
                "| Metric | Giá trị |",
                "| --- | ---: |",
                f"| active_memory_with_evidence | {mem.active_memory_with_evidence:.3f} |",
                f"| retrieval MRR | {ret.mrr:.3f} |",
                f"| retrieval precision@k | {ret.precision_at_k:.3f} |",
                f"| patch test_pass_rate | {patch.test_pass_rate:.3f} |",
                f"| safety violations | {mem.safety_violation_count} |",
                f"| tier | {agg.tier} |",
                "",
            ]
        )
    if ollama is not None:
        lines.append("### Ollama (`ollama_latest.json`)")
        lines.append("")
        lines.append(f"- Model: `{ollama.ollama_model}`")
        lines.append(
            f"- Tokens: {ollama.cost.total_tokens} "
            f"(in={ollama.cost.total_input_tokens}, out={ollama.cost.total_output_tokens})"
        )
        lines.append(f"- Latency: {ollama.cost.total_latency_ms} ms")
        lines.append(
            f"- Harness / LLM / blended: "
            f"{ollama.aggregate.harness_system_score:.4f} / "
            f"{ollama.aggregate.llm_system_score:.4f} / "
            f"{ollama.aggregate.system_score:.4f}"
        )
        lines.append("")

    lines.append("## 4. Lịch sử & xu hướng")
    lines.append("")
    history = load_benchmark_history(history_path, limit=10)
    if history:
        blended = [e.blended_score for e in history]
        low, high = min(blended), max(blended)
        spark = "▁▂▃▄▅▆▇█"
        if high > low:
            chars = "".join(
                spark[int((v - low) / (high - low) * (len(spark) - 1))] for v in blended
            )
        else:
            chars = spark[-1] * len(blended)
        lines.append(f"- Sparkline blended ({len(history)} runs): `{chars}`")
        lines.append("")
        lines.append("```text")
        lines.append(render_trend_table(history))
        lines.append("```")
    else:
        lines.append("_Chưa có `history.jsonl`._")
    lines.append("")

    lines.append("## 5. Phase E — deliverables")
    lines.extend(
        [
            "",
            "| Tiêu chí | Deliverable |",
            "| --- | --- |",
            "| Adversarial pack | `golden_tasks/adversarial/` + `--with-adversarial` |",
            "| History regression | `benchmark-regression-gate` + `--enforce-history` |",
            "| Model comparison | `benchmark-compare-models` → `compare/*/comparison.md` |",
            "| Dashboard | `benchmark-dashboard` → `dashboard.md` |",
            "| Release gate | `scripts/release-gate.ps1` + workflow self-hosted |",
            "",
        ]
    )

    compare_latest = report_dir / "compare" / "latest_comparison.md"
    if compare_latest.exists():
        lines.append("## 6. So sánh model")
        lines.append("")
        lines.append(compare_latest.read_text(encoding="utf-8").strip())
        lines.append("")

    flagged_report = ollama or golden
    if flagged_report is not None:
        lines.append("## 7. Task cần chú ý (replay)")
        lines.append("")
        lines.append("```text")
        lines.append(
            render_replay_report(flagged_report, llm_alert_below=0.70, only_flagged=True)
        )
        lines.append("```")
        lines.append("")

    if adversarial is not None:
        lines.append("## 8. Golden + adversarial — bảng task")
        lines.append("")
        lines.append(render_summary_table(adversarial))
        lines.append("")

    if golden is not None and adversarial is None:
        lines.append("## 8. Golden — bảng task")
        lines.append("")
        lines.append(render_summary_table(golden))
        lines.append("")

    lines.append("## 9. Artifact & lệnh")
    lines.append("")
    lines.append("| File | Mô tả |")
    lines.append("| --- | --- |")
    artifacts = [
        (report_dir / "overall_summary.md", "Báo cáo này"),
        (report_dir / "dashboard.md", "Dashboard ngắn"),
        (report_dir / "latest.json", "Golden harness"),
        (report_dir / "ollama_latest.json", "Golden + Ollama"),
        (report_dir / "adversarial_latest.json", "32 task + adversarial"),
        (report_dir / "history.jsonl", "Lịch sử run"),
        (report_dir / "performance_optimization_summary.md", "Tối ưu hiệu năng"),
        (pipeline_summary_path, "Pipeline doctor → benchmark"),
        (phase_gate_path, "Phase 1–11 gates"),
        (Path("docs/benchmark-release-gate.md"), "Hướng dẫn release gate"),
    ]
    for path, desc in artifacts:
        if path.exists():
            lines.append(f"| `{path.as_posix()}` | {desc} |")
    lines.append("")
    lines.append("```powershell")
    lines.append(".\\scripts\\release-gate.ps1 -SkipModelCompare")
    lines.append(".\\.venv\\Scripts\\python -m ai_local.cli benchmark-overall-summary")
    lines.append(".\\.venv\\Scripts\\python -m ai_local.cli benchmark-dashboard")
    lines.append(".\\.venv\\Scripts\\python -m ai_local.cli benchmark-trend --last 10")
    lines.append("```")
    lines.append("")

    if pipeline_summary_path.exists():
        lines.append("## 10. Pipeline gần nhất")
        lines.append("")
        text = pipeline_summary_path.read_text(encoding="utf-8")
        for line in text.splitlines()[:25]:
            lines.append(line)
        if len(text.splitlines()) > 25:
            lines.append("")
            lines.append(f"_…xem đầy đủ tại `{pipeline_summary_path.as_posix()}`._")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return output_path
