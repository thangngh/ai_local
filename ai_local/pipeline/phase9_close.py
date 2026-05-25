from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.pipeline.replay import Phase9ReplayResult, run_phase9_replay_fixtures
from ai_local.pipeline.stress import Phase9StressResult, run_phase9_stress_cases


@dataclass(frozen=True)
class Phase9CloseResult:
    passed: bool
    replay_results: list[Phase9ReplayResult]
    stress_results: list[Phase9StressResult]

    @property
    def replay_passed(self) -> int:
        return sum(1 for result in self.replay_results if result.passed)

    @property
    def stress_passed(self) -> int:
        return sum(1 for result in self.stress_results if result.passed)

    @property
    def replay_total(self) -> int:
        return len(self.replay_results)

    @property
    def stress_total(self) -> int:
        return len(self.stress_results)

    @property
    def reasons(self) -> list[str]:
        reasons: list[str] = []
        for replay_result in self.replay_results:
            reasons.extend(replay_result.reasons)
        for stress_result in self.stress_results:
            reasons.extend(stress_result.reasons)
        return reasons


def run_phase9_close(
    *,
    replay_config: Path,
    stress_config: Path,
    workspace_root: Path,
    patch_levels_config: Path,
    audit_db: Path | None = None,
) -> Phase9CloseResult:
    replay_results = run_phase9_replay_fixtures(
        config_path=replay_config,
        workspace_root=workspace_root / "replay",
        patch_levels_config=patch_levels_config,
        audit_db=audit_db,
    )
    stress_results = run_phase9_stress_cases(
        config_path=stress_config,
        workspace_root=workspace_root / "stress",
    )
    passed = all(result.passed for result in replay_results) and all(
        result.passed for result in stress_results
    )
    return Phase9CloseResult(
        passed=passed,
        replay_results=replay_results,
        stress_results=stress_results,
    )
