from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.benchmark.runner import run_golden_benchmark, write_benchmark_report


@dataclass(frozen=True)
class HistorySeedProfile:
    name: str
    include_adversarial: bool
    with_ollama: bool
    output: Path
    task_pack: str


PROFILES: tuple[HistorySeedProfile, ...] = (
    HistorySeedProfile(
        name="golden_harness",
        include_adversarial=False,
        with_ollama=False,
        output=Path(".reports/benchmark/history_seed_golden_harness.json"),
        task_pack="golden",
    ),
    HistorySeedProfile(
        name="golden_ollama",
        include_adversarial=False,
        with_ollama=True,
        output=Path(".reports/benchmark/history_seed_golden_ollama.json"),
        task_pack="golden",
    ),
    HistorySeedProfile(
        name="adversarial_harness",
        include_adversarial=True,
        with_ollama=False,
        output=Path(".reports/benchmark/history_seed_adversarial_harness.json"),
        task_pack="golden+adversarial",
    ),
    HistorySeedProfile(
        name="adversarial_ollama",
        include_adversarial=True,
        with_ollama=True,
        output=Path(".reports/benchmark/adversarial_ollama_latest.json"),
        task_pack="golden+adversarial",
    ),
)


def seed_history_baseline(
    *,
    runs_per_profile: int = 10,
    profiles: tuple[HistorySeedProfile, ...] = PROFILES,
    tasks_root: Path = Path("golden_tasks"),
    history_path: Path = Path(".reports/benchmark/history.jsonl"),
    ollama_config_path: Path = Path("configs/benchmark_ollama.yaml"),
    ollama_prompt_path: Path = Path("configs/benchmark_ollama_prompt.yaml"),
) -> dict[str, int]:
    from ai_local.benchmark.ollama_eval import OllamaBenchmarkConfig, load_ollama_prompt_config
    from ai_local.benchmark.runner import load_ollama_benchmark_config as load_ollama_yaml

    completed: dict[str, int] = {}
    base_ollama = load_ollama_yaml(ollama_config_path)
    prompt_cfg = (
        load_ollama_prompt_config(ollama_prompt_path) if ollama_prompt_path.exists() else None
    )

    for profile in profiles:
        count = 0
        for _ in range(runs_per_profile):
            ollama_settings = None
            if profile.with_ollama:
                ollama_settings = OllamaBenchmarkConfig(
                    base_url=base_ollama.base_url,
                    model=base_ollama.model,
                    timeout_seconds=base_ollama.timeout_seconds,
                    harness_weight=base_ollama.harness_weight,
                    input_usd_per_1m=base_ollama.input_usd_per_1m,
                    output_usd_per_1m=base_ollama.output_usd_per_1m,
                )
            report = run_golden_benchmark(
                tasks_root=tasks_root,
                benchmark_id=f"history_seed_{profile.name}",
                include_adversarial=profile.include_adversarial,
                ollama_config=ollama_settings,
                ollama_prompt_config=prompt_cfg,
            )
            write_benchmark_report(
                report,
                profile.output,
                append_history=True,
                task_pack=profile.task_pack,
                write_summary=False,
            )
            count += 1
        completed[profile.name] = count
    return completed
