from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ai_local.benchmark.ollama_eval import OllamaBenchmarkConfig, OllamaPromptConfig, load_ollama_prompt_config
from ai_local.benchmark.runner import (
    benchmark_task_pack,
    load_ollama_benchmark_config,
    run_golden_benchmark,
    write_benchmark_report,
)
from ai_local.benchmark.split_reports import write_split_score_reports
from ai_local.config.loader import load_yaml
from ai_local.llm.ollama import OllamaClient, OllamaConfig, OllamaError


@dataclass(frozen=True)
class ModelCompareSpec:
    name: str


@dataclass(frozen=True)
class ModelCompareDefaults:
    with_adversarial: bool
    harness_weight: float
    ollama_config: Path
    ollama_prompt_config: Path
    tasks_root: Path
    report_dir: Path


def load_model_compare_config(config_path: Path) -> tuple[list[ModelCompareSpec], ModelCompareDefaults]:
    data = load_yaml(config_path)
    models_raw = data.get("models", [])
    defaults_raw = data.get("defaults", {})
    if not isinstance(models_raw, list):
        models_raw = []
    if not isinstance(defaults_raw, dict):
        defaults_raw = {}
    models = [
        ModelCompareSpec(name=str(item["name"]))
        for item in models_raw
        if isinstance(item, dict) and "name" in item
    ]
    defaults = ModelCompareDefaults(
        with_adversarial=bool(defaults_raw.get("with_adversarial", False)),
        harness_weight=float(defaults_raw.get("harness_weight", 0.5)),
        ollama_config=Path(str(defaults_raw.get("ollama_config", "configs/benchmark_ollama.yaml"))),
        ollama_prompt_config=Path(
            str(defaults_raw.get("ollama_prompt_config", "configs/benchmark_ollama_prompt.yaml"))
        ),
        tasks_root=Path(str(defaults_raw.get("tasks_root", "golden_tasks"))),
        report_dir=Path(str(defaults_raw.get("report_dir", ".reports/benchmark/compare"))),
    )
    return models, defaults


def _ollama_parse_rate(report) -> float | None:
    from ai_local.benchmark.history import _ollama_parse_rate

    return _ollama_parse_rate(report)


def run_model_comparison(
    *,
    models_config: Path,
    with_adversarial: bool | None = None,
    skip_unavailable_models: bool = True,
) -> Path:
    models, defaults = load_model_compare_config(models_config)
    include_adversarial = (
        defaults.with_adversarial if with_adversarial is None else with_adversarial
    )
    task_pack = benchmark_task_pack(include_adversarial=include_adversarial)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    output_dir = defaults.report_dir / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    base_ollama = load_ollama_benchmark_config(defaults.ollama_config)
    prompt_settings: OllamaPromptConfig | None = None
    if defaults.ollama_prompt_config.exists():
        prompt_settings = load_ollama_prompt_config(defaults.ollama_prompt_config)

    rows: list[dict[str, object]] = []
    for spec in models:
        client = OllamaClient(
            OllamaConfig(
                base_url=base_ollama.base_url,
                model=spec.name,
                timeout_seconds=base_ollama.timeout_seconds,
            )
        )
        if not client.health_check():
            if skip_unavailable_models:
                rows.append({"model": spec.name, "status": "skipped", "reason": "ollama_unreachable"})
                continue
            msg = f"Ollama is not reachable at {base_ollama.base_url}"
            raise OllamaError(msg)
        try:
            client.ensure_model(spec.name)
        except OllamaError as exc:
            if skip_unavailable_models:
                rows.append({"model": spec.name, "status": "skipped", "reason": str(exc)})
                continue
            raise

        ollama_settings = OllamaBenchmarkConfig(
            base_url=base_ollama.base_url,
            model=spec.name,
            timeout_seconds=base_ollama.timeout_seconds,
            harness_weight=defaults.harness_weight,
            input_usd_per_1m=base_ollama.input_usd_per_1m,
            output_usd_per_1m=base_ollama.output_usd_per_1m,
        )
        report = run_golden_benchmark(
            tasks_root=defaults.tasks_root,
            benchmark_id=f"compare_{spec.name.replace(':', '_')}",
            ollama_config=ollama_settings,
            ollama_prompt_config=prompt_settings,
            include_adversarial=include_adversarial,
        )
        model_dir = output_dir / spec.name.replace(":", "_")
        model_dir.mkdir(parents=True, exist_ok=True)
        report_path = model_dir / "report.json"
        write_benchmark_report(
            report,
            report_path,
            append_history=True,
            task_pack=task_pack,
        )
        write_split_score_reports(report, model_dir)
        rows.append(
            {
                "model": spec.name,
                "status": "ok",
                "run_id": report.run_id,
                "harness_score": report.aggregate.harness_system_score,
                "llm_score": report.aggregate.llm_system_score,
                "blended_score": report.aggregate.system_score,
                "total_tokens": report.cost.total_tokens,
                "parse_rate": _ollama_parse_rate(report),
                "pass_count": report.aggregate.pass_count,
                "total": report.aggregate.total,
                "latency_ms": report.cost.total_latency_ms,
                "report_path": str(report_path),
            }
        )

    comparison = {"generated_at": datetime.now(UTC).isoformat(), "pack": task_pack, "models": rows}
    json_path = output_dir / "comparison.json"
    json_path.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path = output_dir / "comparison.md"
    md_path.write_text(_render_comparison_markdown(comparison), encoding="utf-8")
    latest_link = defaults.report_dir / "latest_comparison.md"
    latest_link.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    return md_path


def _render_comparison_markdown(comparison: dict[str, object]) -> str:
    lines = [
        "# Benchmark model comparison",
        "",
        f"Generated: {comparison.get('generated_at', '')}",
        f"Pack: {comparison.get('pack', 'golden')}",
        "",
        "| model | status | harness | llm | blended | tokens | parse | pass | latency_ms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for row in comparison.get("models", []):
        if not isinstance(row, dict):
            continue
        llm = row.get("llm_score")
        llm_text = f"{float(llm):.3f}" if isinstance(llm, (int, float)) else "-"
        parse = row.get("parse_rate")
        parse_text = f"{float(parse):.3f}" if isinstance(parse, (int, float)) else "-"
        blended = row.get("blended_score")
        blended_text = f"{float(blended):.3f}" if isinstance(blended, (int, float)) else "-"
        harness = row.get("harness_score")
        harness_text = f"{float(harness):.3f}" if isinstance(harness, (int, float)) else "-"
        lines.append(
            f"| {row.get('model', '')} | {row.get('status', '')} | {harness_text} | "
            f"{llm_text} | {blended_text} | {row.get('total_tokens', '-')} | {parse_text} | "
            f"{row.get('pass_count', '-')}/{row.get('total', '-')} | {row.get('latency_ms', '-')} |"
        )
    return "\n".join(lines) + "\n"
