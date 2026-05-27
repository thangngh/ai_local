from __future__ import annotations

import json
from pathlib import Path

from ai_local.benchmark.regression import enforce_regression_gate_from_paths, load_regression_policy
from ai_local.benchmark.runner import run_golden_benchmark, write_benchmark_report


def test_regression_gate_fails_on_score_drop(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    history_path = report_dir / "history.jsonl"
    policy = load_regression_policy(Path("configs/benchmark_regression.yaml"))
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        "regression:\n"
        "  baseline_strategy: median\n"
        "  baseline_last_n: 5\n"
        "  min_baseline_entries: 2\n"
        "  max_drop_blended_score: 0.01\n"
        "  max_drop_harness_score: 0.01\n"
        "  max_drop_llm_score: 0.05\n"
        "  max_drop_active_memory_with_evidence: 0.05\n"
        "  max_drop_retrieval_mrr: 0.08\n"
        "  max_drop_parse_rate: 0.10\n"
        "  max_drop_pass_count: 0\n",
        encoding="utf-8",
    )
    policy = load_regression_policy(policy_path)

    for _ in range(2):
        report = run_golden_benchmark(tasks_root=Path("golden_tasks"), benchmark_id="reg_test")
        write_benchmark_report(
            report,
            report_dir / "baseline.json",
            append_history=True,
            task_pack="golden",
        )

    good = run_golden_benchmark(tasks_root=Path("golden_tasks"), benchmark_id="reg_test")
    good_path = report_dir / "good.json"
    write_benchmark_report(good, good_path, append_history=False, task_pack="golden")

    bad_payload = json.loads(good_path.read_text(encoding="utf-8"))
    bad_payload["aggregate"]["system_score"] = 0.5
    bad_payload["aggregate"]["harness_system_score"] = 0.5
    bad_path = report_dir / "bad.json"
    bad_path.write_text(json.dumps(bad_payload, indent=2) + "\n", encoding="utf-8")

    violations = enforce_regression_gate_from_paths(
        report_path=bad_path,
        history_path=history_path,
        policy=policy,
        task_pack="golden",
    )
    assert violations
    assert any("blended_score" in item or "harness_score" in item for item in violations)
