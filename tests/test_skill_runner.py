import sys
from pathlib import Path

from ai_local.audit.store import InMemoryAuditStore
from ai_local.skills.models import SkillScriptRequest, SkillScriptRunRequest
from ai_local.skills.runner import SkillScriptRunner
from ai_local.skills.runtime import verify_skill_package
from ai_local.skills.models import SkillPackageManifest, SkillPackageTrustResult
from ai_local.tools.registry import ToolRegistry
from ai_local.tools.schemas import ToolDefinition


def _trusted_package() -> SkillPackageTrustResult:
    return verify_skill_package(
        SkillPackageManifest(
            package_id="pkg.simple-workflow",
            skill_id="simple-workflow",
            source_ref="local://skills/simple-workflow",
            checksum="sha256:abc123",
            trusted=True,
            manifest_identity="simple-workflow",
        ),
        expected_checksum="sha256:abc123",
        allowed_source_prefixes=["local://skills/"],
    )


def _registry(*, timeout_seconds: int = 5) -> ToolRegistry:
    return ToolRegistry(
        {
            "skill.python": ToolDefinition.model_validate(
                {
                    "name": "skill.python",
                    "command": [sys.executable, "-c"],
                    "side_effect_level": "process",
                    "timeout_seconds": timeout_seconds,
                    "audit_required": True,
                    "approval_required": True,
                    "risk_level": "medium",
                }
            )
        }
    )


def _script_request(*, approved: bool = True) -> SkillScriptRequest:
    return SkillScriptRequest(
        package=_trusted_package(),
        script_id="run-python",
        tool_name="skill.python",
        declared_tools=["skill.python"],
        approved=approved,
        output_has_evidence_refs=True,
    )


def test_skill_script_runner_executes_allowlisted_subprocess_and_audits(tmp_path: Path) -> None:
    audit = InMemoryAuditStore()
    runner = SkillScriptRunner(_registry(), workspace_root=tmp_path, audit_store=audit)

    result = runner.run(
        SkillScriptRunRequest(
            script=_script_request(),
            argv=["print('ok')"],
            cwd=".",
        )
    )

    assert result.decision == "succeeded"
    assert result.return_code == 0
    assert result.stdout.strip() == "ok"
    assert result.next_gate == "evidence_rank"
    assert result.command[:2] == [sys.executable, "-c"]
    assert audit.list_events()[0].action == "skill.script.run"
    assert audit.list_events()[0].result == "succeeded"


def test_skill_script_runner_routes_subprocess_failure_to_patch_pipeline(tmp_path: Path) -> None:
    runner = SkillScriptRunner(_registry(), workspace_root=tmp_path)

    result = runner.run(
        SkillScriptRunRequest(
            script=_script_request(),
            argv=["import sys; sys.stderr.write('bad'); sys.exit(7)"],
        )
    )

    assert result.decision == "failed"
    assert result.return_code == 7
    assert result.stderr == "bad"
    assert result.next_gate == "patch_pipeline"


def test_skill_script_runner_requires_approval_before_side_effect_process(
    tmp_path: Path,
) -> None:
    runner = SkillScriptRunner(_registry(), workspace_root=tmp_path)

    result = runner.run(
        SkillScriptRunRequest(
            script=_script_request(approved=False),
            argv=["print('should not run')"],
        )
    )

    assert result.decision == "ask_user"
    assert result.reason == "script side effect requires approval or trusted package policy"
    assert result.command == []
    assert result.next_gate == "confirmation"


def test_skill_script_runner_denies_cwd_escape_and_missing_command(tmp_path: Path) -> None:
    no_command = ToolRegistry(
        {
            "skill.noop": ToolDefinition(
                name="skill.noop",
                side_effect_level="read",
                timeout_seconds=5,
                audit_required=True,
                approval_required=False,
                risk_level="low",
            )
        }
    )
    no_command_runner = SkillScriptRunner(no_command, workspace_root=tmp_path)
    escape_runner = SkillScriptRunner(_registry(), workspace_root=tmp_path)

    missing_command = no_command_runner.run(
        SkillScriptRunRequest(
            script=SkillScriptRequest(
                package=_trusted_package(),
                script_id="noop",
                tool_name="skill.noop",
                declared_tools=["skill.noop"],
                output_has_evidence_refs=True,
            ),
        )
    )
    cwd_escape = escape_runner.run(
        SkillScriptRunRequest(
            script=_script_request(),
            argv=["print('no')"],
            cwd="..",
        )
    )

    assert missing_command.decision == "denied"
    assert missing_command.reason == "script tool has no subprocess command"
    assert cwd_escape.decision == "denied"
    assert cwd_escape.reason == "script cwd escapes workspace root"
    assert cwd_escape.next_gate == "stop"


def test_skill_script_runner_enforces_tool_timeout(tmp_path: Path) -> None:
    runner = SkillScriptRunner(_registry(timeout_seconds=1), workspace_root=tmp_path)

    result = runner.run(
        SkillScriptRunRequest(
            script=_script_request(),
            argv=["import time; time.sleep(3)"],
            timeout_seconds=5,
        )
    )

    assert result.decision == "timed_out"
    assert result.timeout_seconds == 1
    assert result.next_gate == "patch_pipeline"
