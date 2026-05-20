from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.composite_gate import load_composite_gates, run_composite_promotion


ROOT = Path(__file__).resolve().parents[2]


def test_composite_gate_count_is_ten() -> None:
    gates = load_composite_gates(ROOT / "configs" / "composite_gates.yaml")

    assert len(gates) == 10
    assert [gate.id for gate in gates][0] == "G01_TASK_INTAKE_SOURCE_COVERAGE"
    assert [gate.id for gate in gates][-1] == "G10_DEEP_HOP_FULL_CHAIN_SECURITY"


def test_composite_gate_levels_and_hop_depths() -> None:
    results = run_composite_promotion(config_path=ROOT / "configs" / "composite_gates.yaml")

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert [result.max_hop_depth for result in results] == [3, 6, 15, 20]
    assert all(result.passed for result in results)


def test_extreme_composite_gate_covers_required_modules() -> None:
    data = load_yaml(ROOT / "configs" / "composite_gates.yaml")
    required_modules = set(data["required_modules"])
    gates = load_composite_gates(ROOT / "configs" / "composite_gates.yaml")
    extreme_modules = {module for gate in gates if gate.level == "extreme" for module in gate.modules}

    assert required_modules.issubset(extreme_modules)


def test_security_aliases_include_user_term() -> None:
    data = load_yaml(ROOT / "configs" / "composite_gates.yaml")

    assert "security" in data["security_aliases"]
    assert "secrior" in data["security_aliases"]

