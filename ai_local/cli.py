from pathlib import Path

import typer

from ai_local.harness.test_gate import run_patch_gate, run_promoted_gates
from ai_local.harness.noise_gate import run_noise_promotion
from ai_local.harness.memory_regression_gate import run_memory_regression_promotion
from ai_local.harness.memory_layer_gate import run_memory_layer_promotion
from ai_local.harness.composite_gate import run_composite_promotion
from ai_local.harness.decision_gate import run_decision_promotion
from ai_local.harness.retrieval_gate import run_retrieval_promotion
from ai_local.harness.agent_loop_gate import run_agent_loop_promotion
from ai_local.harness.big_harness import load_big_harness_policy, validate_big_harness_policy
from ai_local.harness.small_patch_harness import run_small_patch_policy_check
from ai_local.harness.patch_pipeline_harness import run_patch_pipeline_promotion
from ai_local.harness.patch_levels import load_patch_levels, validate_patch_levels
from ai_local.harness.evaluation_gate import run_evaluation_promotion
from ai_local.harness.confirmation_gate import run_confirmation_promotion
from ai_local.harness.knowledge_gate import run_knowledge_promotion
from ai_local.harness.evidence_rank_gate import run_evidence_rank_promotion
from ai_local.harness.tool_combo_gate import run_tool_combo_promotion
from ai_local.harness.skill_gate import run_skill_promotion
from ai_local.harness.memory_sql_gate import run_memory_sql_promotion
from ai_local.harness.conflict_path_gate import run_conflict_path_promotion
from ai_local.harness.multi_instance_conflict_gate import (
    run_multi_instance_conflict_promotion,
)
from ai_local.harness.request_lifecycle_gate import run_request_lifecycle_promotion
from ai_local.harness.prompt_injection_refusal_gate import (
    run_prompt_injection_refusal_promotion,
)
from ai_local.harness.thread_control_gate import run_thread_control_promotion

app = typer.Typer()


@app.command()
def gate(
    commands: list[str] = typer.Argument(...),
    config: Path = typer.Option(Path("configs/tools.yaml")),
    cwd: Path = typer.Option(Path(".")),
) -> None:
    if commands and commands[0] == "gate":
        commands = commands[1:]
    results = run_patch_gate(commands, config_path=config, cwd=cwd)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(f"{status} {result.command_id} exit={result.exit_code}")
        if not result.passed:
            failed = True
            if result.stderr:
                typer.echo(result.stderr)
    if failed:
        raise typer.Exit(code=1)


@app.command()
def promote(
    max_level: str | None = typer.Option(None),
    gates_config: Path = typer.Option(Path("configs/gates.yaml")),
    tools_config: Path = typer.Option(Path("configs/tools.yaml")),
    cwd: Path = typer.Option(Path(".")),
) -> None:
    level_results = run_promoted_gates(
        gates_config_path=gates_config,
        tools_config_path=tools_config,
        cwd=cwd,
        max_level=max_level,
    )
    failed = False
    for level_result in level_results:
        typer.echo(f"[{level_result.level}]")
        for result in level_result.results:
            status = "PASS" if result.passed else "FAIL"
            typer.echo(f"{status} {result.command_id} exit={result.exit_code}")
            if not result.passed:
                failed = True
                if result.stderr:
                    typer.echo(result.stderr)
        if not level_result.passed:
            typer.echo(f"STOP promotion at {level_result.level}")
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def noise(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/noise_gates.yaml")),
) -> None:
    results = run_noise_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"checks={len(result.checked_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def memory_regression(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/memory_regression_gates.yaml")),
) -> None:
    results = run_memory_regression_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_state_hops={result.max_state_hops} "
            f"checks={len(result.checked_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def memory_layers(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/memory_layer_gates.yaml")),
) -> None:
    results = run_memory_layer_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"layers={len(result.checked_layers)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def composite(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/composite_gates.yaml")),
) -> None:
    results = run_composite_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"gates={len(result.checked_gate_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def decision(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/decision_gates.yaml")),
) -> None:
    results = run_decision_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def retrieval(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/retrieval_gates.yaml")),
) -> None:
    results = run_retrieval_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def agent_loop(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/agent_loop_gates.yaml")),
) -> None:
    results = run_agent_loop_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def big_harness(config: Path = typer.Option(Path("configs/big_harness.yaml"))) -> None:
    policy = load_big_harness_policy(config)
    errors = validate_big_harness_policy(policy)
    if errors:
        for error in errors:
            typer.echo(f"FAIL {error}")
        raise typer.Exit(code=1)
    typer.echo(
        "PASS big_harness "
        f"max_steps={policy.max_steps} max_tool_calls={policy.max_tool_calls} "
        f"max_hop_depth={policy.max_hop_depth}"
    )


@app.command()
def small_patch(config: Path = typer.Option(Path("configs/small_patch_harness.yaml"))) -> None:
    results = run_small_patch_policy_check(config)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(f"{status} {result.level}")
        if not result.passed:
            failed = True
            typer.echo(result.reason)
    if failed:
        raise typer.Exit(code=1)


@app.command()
def patch_pipeline(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/patch_pipeline_harness.yaml")),
) -> None:
    results = run_patch_pipeline_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def patch_levels(config: Path = typer.Option(Path("configs/patch_levels.yaml"))) -> None:
    levels = load_patch_levels(config)
    errors = validate_patch_levels(levels)
    if errors:
        for error in errors:
            typer.echo(f"FAIL {error}")
        raise typer.Exit(code=1)
    for level in levels:
        typer.echo(
            f"PASS {level.name} files={level.max_files_changed} "
            f"lines={level.max_changed_lines} hop={level.max_hop_depth} "
            f"risk={level.risk_ceiling}"
        )


@app.command()
def evaluation(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/evaluation_gates.yaml")),
) -> None:
    results = run_evaluation_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def confirmation(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/confirmation_gates.yaml")),
) -> None:
    results = run_confirmation_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def knowledge(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/knowledge_gates.yaml")),
) -> None:
    results = run_knowledge_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def evidence_rank(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/evidence_rank_gates.yaml")),
) -> None:
    results = run_evidence_rank_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def tool_combo(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/tool_combo_gates.yaml")),
) -> None:
    results = run_tool_combo_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def skills(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/skill_gates.yaml")),
    root: Path = typer.Option(Path(".")),
) -> None:
    results = run_skill_promotion(config_path=config, root=root, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def memory_sql(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/memory_sql_gates.yaml")),
) -> None:
    results = run_memory_sql_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def conflict_paths(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/conflict_path_gates.yaml")),
) -> None:
    results = run_conflict_path_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def multi_conflict(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/multi_instance_conflict_gates.yaml")),
) -> None:
    results = run_multi_instance_conflict_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def request_lifecycle(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/request_lifecycle_gates.yaml")),
) -> None:
    results = run_request_lifecycle_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def prompt_injection(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/prompt_injection_refusal_gates.yaml")),
) -> None:
    results = run_prompt_injection_refusal_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def thread_control(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/thread_control_gates.yaml")),
) -> None:
    results = run_thread_control_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)























if __name__ == "__main__":
    app()
