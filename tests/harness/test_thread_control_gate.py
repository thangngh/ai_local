from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.thread_control_gate import (
    ThreadControlCase,
    infer_thread_control_decision,
    load_thread_control_levels,
    run_thread_control_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_thread_control_levels_scale_to_hop_50() -> None:
    levels = load_thread_control_levels(ROOT / "configs" / "thread_control_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [6, 15, 30, 50]


def test_thread_control_promotion_passes() -> None:
    results = run_thread_control_promotion(
        config_path=ROOT / "configs" / "thread_control_gates.yaml"
    )

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)


def test_thread_control_modules_include_multi_module_bridge() -> None:
    data = load_yaml(ROOT / "configs" / "thread_control_gates.yaml")

    assert "THREAD_CONTROL" in data["thread_control_modules"]
    assert "PROMPT_INJECTION_GATE" in data["thread_control_modules"]
    assert "OUTBOX" in data["thread_control_modules"]
    assert data["max_supported_hop_depth"] == 50


def test_retrieved_content_cannot_control_thread() -> None:
    case = ThreadControlCase(
        id="unit",
        flow=["USER", "GATEWAY", "RETRIEVER", "THREAD_CONTROL", "DECISION_GATE"],
        control_event="archive",
        authority="retrieved_content",
        conflict_type="prompt_injection_control",
        expected_decision="refuse_control_event",
        hop_depth=30,
    )

    assert infer_thread_control_decision(case) == "refuse_control_event"


def test_deep_invalid_thread_path_stops() -> None:
    case = ThreadControlCase(
        id="unit",
        flow=["USER", "GATEWAY", "THREAD_CONTROL", "STOP"],
        control_event="resume",
        authority="mixed_instances",
        conflict_type="all_paths_invalid",
        expected_decision="stop",
        hop_depth=50,
    )

    assert infer_thread_control_decision(case) == "stop"
