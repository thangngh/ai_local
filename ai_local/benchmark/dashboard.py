from __future__ import annotations

import json
from pathlib import Path

from ai_local.benchmark.history import load_benchmark_history
from ai_local.benchmark.release_decision import compute_release_decision
from ai_local.benchmark.replay import load_benchmark_report, render_replay_report
from ai_local.benchmark.regression import compute_regression_baseline, load_regression_policy


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


def _score_from_split_file(path: Path | None) -> str:
    if path is None or not path.exists():
        return "MISSING"
    payload = json.loads(path.read_text(encoding="utf-8"))
    value = payload.get("aggregate_score")
    if value is None:
        return "MISSING"
    return f"{float(value):.4f}"


def _score_from_report(path: Path | None, *, field: str) -> str:
    if path is None or not path.exists():
        return "MISSING"
    report = load_benchmark_report(path)
    if field == "harness":
        return f"{report.aggregate.harness_system_score:.4f}"
    if field == "llm":
        if report.aggregate.llm_system_score is None:
            return "MISSING"
        return f"{report.aggregate.llm_system_score:.4f}"
    return f"{report.aggregate.system_score:.4f}"


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
    adversarial_ollama_path = report_dir / "adversarial_ollama_latest.json"
    history_path = report_dir / "history.jsonl"

    release = compute_release_decision(
        report_dir,
        thresholds_config=thresholds_config,
        regression_config=regression_config,
    )

    sections: list[str] = ["# Benchmark dashboard", ""]

    sections.append("## RELEASE DECISION")
    sections.append("")
    sections.append(f"**RELEASE DECISION: {release.decision}**")
    sections.append("")
    sections.append("Reasons:")
    for reason in release.reasons:
        sections.append(f"- {reason}")
    sections.append("")

    last_run_id = "-"
    last_mode = "-"
    if latest_path.exists():
        golden = load_benchmark_report(latest_path)
        last_run_id = golden.run_id
        last_mode = golden.run_mode

    sections.append("## 1. Executive")
    sections.append(f"- Gate decision: **{release.decision}**")
    sections.append(f"- Last golden run: `{last_run_id}` mode=`{last_mode}`")
    sections.append("")

    sections.append("## 2. Score separation")
    harness_split = report_dir / "latest_harness_scores.json"
    llm_split = report_dir / "latest_llm_scores.json"
    blended_split = report_dir / "latest_blended_scores.json"
    if not harness_split.exists():
        harness_split = _latest_glob(report_dir, "*_harness_scores.json")
    if not llm_split.exists():
        llm_split = _latest_glob(report_dir, "*_llm_scores.json")
    if not blended_split.exists():
        blended_split = _latest_glob(report_dir, "*_blended_scores.json")

    golden_harness = _score_from_report(latest_path, field="harness")
    golden_llm = _score_from_report(ollama_path, field="llm")
    golden_blended = _score_from_report(ollama_path, field="blended")
    if golden_blended == "MISSING":
        golden_blended = _score_from_report(latest_path, field="blended")

    sections.append(f"- golden harness: {golden_harness} (split: {_score_from_split_file(harness_split)})")
    sections.append(f"- golden llm: {golden_llm} (split: {_score_from_split_file(llm_split)})")
    sections.append(f"- golden blended: {golden_blended} (split: {_score_from_split_file(blended_split)})")
    if adversarial_path.exists():
        adv = load_benchmark_report(adversarial_path)
        sections.append(
            f"- adversarial harness: {adv.aggregate.harness_system_score:.4f} "
            f"({adv.aggregate.pass_count}/{adv.aggregate.total})"
        )
    if adversarial_ollama_path.exists():
        adv_o = load_benchmark_report(adversarial_ollama_path)
        llm = adv_o.aggregate.llm_system_score
        llm_text = f"{llm:.4f}" if llm is not None else "MISSING"
        sections.append(
            f"- adversarial Ollama blended: {adv_o.aggregate.system_score:.4f} llm={llm_text} "
            f"partials={adv_o.aggregate.partial_count}"
        )
    sections.append("")

    if latest_path.exists():
        report = load_benchmark_report(latest_path)
        agg = report.aggregate
        sections.append("## 3. Layer metrics (golden harness)")
        sections.append(
            f"- Memory active_with_evidence: {agg.memory_metrics.active_memory_with_evidence:.3f}"
        )
        sections.append(f"- Retrieval MRR: {agg.retrieval_metrics.mrr:.3f}")
        sections.append(f"- Patch test pass rate: {agg.patch_metrics.test_pass_rate:.3f}")
        sections.append("")

    if ollama_path.exists():
        ollama_report = load_benchmark_report(ollama_path)
        sections.append("## 3b. Ollama run")
        sections.append(f"- Model: `{ollama_report.ollama_model}`")
        sections.append(
            f"- Pass/partial/fail: {ollama_report.aggregate.pass_count}/"
            f"{ollama_report.aggregate.partial_count}/{ollama_report.aggregate.fail_count}"
        )
        sections.append(f"- Tokens: {ollama_report.cost.total_tokens}")
        sections.append("")

    history = load_benchmark_history(history_path, limit=10)
    sections.append("## 4. Trend (last 10 runs)")
    if history:
        blended = [entry.blended_score for entry in history]
        sections.append(f"- Blended sparkline: `{_sparkline(blended)}`")
        sections.append("")
        sections.append("| run_id | pack | mode | blended | harness | llm | pass |")
        sections.append("| --- | --- | --- | ---: | ---: | ---: | --- |")
        for entry in history:
            llm = f"{entry.llm_score:.3f}" if entry.llm_score is not None else "MISSING"
            sections.append(
                f"| {entry.run_id} | {entry.pack} | {entry.run_mode} | "
                f"{entry.blended_score:.3f} | {entry.harness_score:.3f} | {llm} | "
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

    replay_report = ollama_path if ollama_path.exists() else latest_path
    if replay_report.exists():
        report = load_benchmark_report(replay_report)
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
        adversarial_ollama_path,
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
        sections.append("### Adversarial harness latest")
        sections.append(
            f"- score={adv_report.aggregate.harness_system_score:.3f} "
            f"pass={adv_report.aggregate.pass_count}/{adv_report.aggregate.total}"
        )
        if baseline:
            sections.append(f"- regression baseline runs={baseline['baseline_runs']}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(sections).strip() + "\n", encoding="utf-8")
    return output_path
