from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.benchmark.history import load_benchmark_history
from ai_local.benchmark.replay import load_benchmark_report
from ai_local.benchmark.regression import enforce_regression_gate, load_regression_policy
from ai_local.benchmark.thresholds import enforce_thresholds, load_benchmark_thresholds


@dataclass(frozen=True)
class ReleaseDecision:
    decision: str
    reasons: list[str]
    blocking: bool

    @property
    def exit_code(self) -> int:
        if self.decision == "BLOCK":
            return 1
        return 0


def _safety_knowledge_partials(report_path: Path) -> list[str]:
    if not report_path.exists():
        return []
    report = load_benchmark_report(report_path)
    flagged: list[str] = []
    for task in report.tasks:
        if task.category not in {"safety", "knowledge"}:
            continue
        if task.result != "pass" or task.failures:
            llm_val = task.llm_system_score
            flagged.append(
                f"{task.task_id} ({task.category}) result={task.result} "
                f"llm={llm_val} failures={len(task.failures)}"
            )
        if (
            task.result == "partial"
            and task.llm_system_score is not None
            and task.llm_system_score >= 1.0
        ):
            flagged.append(f"{task.task_id} partial with llm_score={task.llm_system_score:.2f} (must be <1.0)")
    return flagged


def _history_mature(history_path: Path, *, min_entries: int = 10) -> bool:
    if not history_path.exists():
        return False
    entries = load_benchmark_history(history_path, limit=min_entries + 1)
    return len(entries) >= min_entries


def compute_release_decision(
    report_dir: Path = Path(".reports/benchmark"),
    *,
    thresholds_config: Path = Path("configs/benchmark_thresholds.yaml"),
    regression_config: Path = Path("configs/benchmark_regression.yaml"),
    history_min_entries: int = 10,
) -> ReleaseDecision:
    reasons: list[str] = []
    blocking = False

    latest = report_dir / "latest.json"
    adversarial = report_dir / "adversarial_latest.json"
    ollama = report_dir / "ollama_latest.json"
    adversarial_ollama = report_dir / "adversarial_ollama_latest.json"
    history_path = report_dir / "history.jsonl"
    thresholds = load_benchmark_thresholds(thresholds_config)
    regression_policy = load_regression_policy(regression_config)

    if latest.exists():
        golden = load_benchmark_report(latest)
        if golden.aggregate.fail_count > 0:
            blocking = True
            reasons.append(f"golden harness fail_count={golden.aggregate.fail_count}")
        th = enforce_thresholds(golden, thresholds, adversarial_pack=False)
        if th:
            blocking = True
            reasons.extend(f"golden threshold: {v}" for v in th)
        else:
            reasons.append("golden harness pass")
    else:
        blocking = True
        reasons.append("missing golden harness report (latest.json)")

    if adversarial.exists():
        adv = load_benchmark_report(adversarial)
        if adv.aggregate.fail_count > 0:
            blocking = True
            reasons.append(f"adversarial harness fail_count={adv.aggregate.fail_count}")
        else:
            reasons.append("adversarial harness pass")
    else:
        reasons.append("adversarial harness report missing")

    if ollama.exists():
        ollama_report = load_benchmark_report(ollama)
        partials = _safety_knowledge_partials(ollama)
        if ollama_report.aggregate.fail_count > 0:
            blocking = True
            reasons.append(f"Ollama golden fail_count={ollama_report.aggregate.fail_count}")
        if partials:
            reasons.append(
                f"Ollama has {len(partials)} safety/knowledge partial or failure task(s)"
            )
            for item in partials[:5]:
                reasons.append(f"  - {item}")
        elif ollama_report.aggregate.partial_count > 0:
            reasons.append(f"Ollama has {ollama_report.aggregate.partial_count} partial task(s)")
        else:
            reasons.append("Ollama golden pass (no partials)")
        th = enforce_thresholds(ollama_report, thresholds, adversarial_pack=False)
        if th:
            blocking = True
            reasons.extend(f"Ollama threshold: {v}" for v in th)
        reg = enforce_regression_gate(
            ollama_report,
            history_path=history_path,
            policy=regression_policy,
            task_pack="golden",
        )
        if reg:
            reasons.append(f"Ollama regression warnings: {len(reg)}")
    else:
        reasons.append("Ollama golden report missing (LLM end-to-end not measured)")

    if adversarial_ollama.exists():
        adv_ollama = load_benchmark_report(adversarial_ollama)
        adv_partials = _safety_knowledge_partials(adversarial_ollama)
        safety_fails = [t for t in adv_ollama.tasks if t.category == "safety" and t.result == "fail"]
        if safety_fails:
            blocking = True
            reasons.append(f"adversarial Ollama safety fail_count={len(safety_fails)}")
        elif adv_partials:
            reasons.append(f"adversarial Ollama safety/knowledge partials={len(adv_partials)}")
        else:
            reasons.append("adversarial Ollama pass (0 safety fail)")
    else:
        reasons.append("adversarial Ollama artifact missing (adversarial_ollama_latest.json)")

    if not _history_mature(history_path, min_entries=history_min_entries):
        reasons.append(
            f"regression history immature (<{history_min_entries} entries in history.jsonl)"
        )

    if blocking:
        decision = "BLOCK"
    elif any(
        "partial" in r.lower()
        or "immature" in r.lower()
        or "missing" in r.lower()
        for r in reasons
    ):
        decision = "PASS_WITH_WARNINGS"
    else:
        decision = "PASS"

    return ReleaseDecision(decision=decision, reasons=reasons, blocking=blocking)
