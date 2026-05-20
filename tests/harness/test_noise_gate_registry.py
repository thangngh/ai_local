from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.noise_gate import load_noise_gate_levels, run_noise_promotion


ROOT = Path(__file__).resolve().parents[2]


def test_noise_gate_levels_promote_from_easy_to_extreme() -> None:
    levels = load_noise_gate_levels(ROOT / "configs" / "noise_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [1, 2, 3, 20]


def test_noise_checks_do_not_exceed_level_hop_depth() -> None:
    levels = load_noise_gate_levels(ROOT / "configs" / "noise_gates.yaml")

    for level in levels:
        assert level.checks
        assert all(check.hop_depth <= level.max_hop_depth for check in level.checks)


def test_noise_hop_depths_are_defined() -> None:
    data = load_yaml(ROOT / "configs" / "noise_gates.yaml")

    assert sorted(data["hop_depths"]) == [1, 2, 3, 4, 5, 20]
    assert data["max_supported_hop_depth"] == 20


def test_noise_promotion_passes_static_gate_definitions() -> None:
    results = run_noise_promotion(config_path=ROOT / "configs" / "noise_gates.yaml")

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)
