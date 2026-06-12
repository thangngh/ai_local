from __future__ import annotations

import json
from pathlib import Path

from ai_local.queue.models import Job, JobStatus
from ai_local.queue.store import SQLiteQueueStore
from ai_local.queue.lifecycle import (
    detect_validation_commands,
    propose_task,
    propose_task_deterministic,
    validate_code_changes_for_apply,
)
from ai_local.runtime.daemon_contract import run_daemon_loop
from ai_local.runtime.worker_contract import ensure_workspace, run_worker_once
from ai_local.llm.ollama import OllamaChatResult
from ai_local.llm.tokens import TokenUsage
from typer.testing import CliRunner

from ai_local.cli import app


class FakeOllamaClient:
    model = "fake-model"

    def chat(self, *, system: str, user: str, model: str | None = None, messages: list[dict[str, str]] | None = None) -> OllamaChatResult:
        return OllamaChatResult(
            content=json.dumps(
                {
                    "analysis": "Update the value.",
                    "reasoning": "The requested file has an exact snippet.",
                    "changes": [
                        {
                            "file": "app.py",
                            "description": "Update value",
                            "original_snippet": "VALUE = 1\n",
                            "new_snippet": "VALUE = 2\n",
                        }
                    ],
                }
            ),
            latency_ms=1,
            model=self.model,
            token_usage=TokenUsage(
                input_tokens=1,
                output_tokens=1,
                total_tokens=2,
                input_chars=len(user),
                output_chars=1,
                token_source="test",
            ),
        )


def test_worker_marks_analysis_as_proposal_ready_not_succeeded(tmp_path: Path) -> None:
    paths = ensure_workspace(tmp_path)
    queue = SQLiteQueueStore(paths["tasks_db"])
    queue.enqueue(Job(id="task-1", type="demo", payload={"task": "Analyze cart store"}))

    result = run_worker_once(tmp_path)
    job = queue.get("task-1")
    artifact_path = paths["reports"] / "worker-task-1.json"

    assert result.status == "pass"
    assert job is not None
    assert job.status == JobStatus.PROPOSAL_READY
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["execution_state"] == "proposal_ready"
    assert artifact["applied"] is False


def test_worker_with_ollama_writes_code_changes_for_apply_flow(tmp_path: Path) -> None:
    paths = ensure_workspace(tmp_path)
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    queue = SQLiteQueueStore(paths["tasks_db"])
    queue.enqueue(Job(id="task-1", type="demo", payload={"task": "Change VALUE to 2 in app.py"}))

    result = run_worker_once(tmp_path, ollama_client=FakeOllamaClient())  # type: ignore[arg-type]
    artifact_path = paths["reports"] / "worker-task-1.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert result.status == "pass"
    assert artifact["llm_used"] is True
    assert artifact["code_changes"][0]["file"] == "app.py"
    assert "They have NOT been applied" in artifact["code_changes_note"]


def test_daemon_loop_passes_ollama_client_to_worker(tmp_path: Path) -> None:
    paths = ensure_workspace(tmp_path)
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    queue = SQLiteQueueStore(paths["tasks_db"])
    queue.enqueue(Job(id="task-1", type="demo", payload={"task": "Change VALUE to 2 in app.py"}))

    iterations = run_daemon_loop(
        workspace=tmp_path,
        poll_interval=0.01,
        max_iterations=1,
        ollama_client=FakeOllamaClient(),  # type: ignore[arg-type]
    )
    artifact = json.loads((paths["reports"] / "worker-task-1.json").read_text(encoding="utf-8"))

    assert iterations == 1
    assert artifact["llm_used"] is True
    assert artifact["code_changes"][0]["file"] == "app.py"


def test_task_approve_apply_validate_snippet_patch(tmp_path: Path) -> None:
    paths = ensure_workspace(tmp_path)
    source = tmp_path / "app.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    queue = SQLiteQueueStore(paths["tasks_db"])
    queue.enqueue(Job(id="task-1", type="demo", status=JobStatus.PROPOSAL_READY, payload={"task": "patch"}))
    artifact_path = paths["reports"] / "worker-task-1.json"
    artifact_path.write_text(
        json.dumps(
            {
                "job_id": "task-1",
                "execution_state": "proposal_ready",
                "applied": False,
                "code_changes": [
                    {
                        "file": "app.py",
                        "description": "Update value",
                        "original_snippet": "VALUE = 1\n",
                        "new_snippet": "VALUE = 2\n",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    runner = CliRunner()

    approved = runner.invoke(app, ["task", "approve", "task-1", "--workspace", str(tmp_path)])
    applied = runner.invoke(app, ["task", "apply", "task-1", "--workspace", str(tmp_path)])
    validated = runner.invoke(app, ["task", "validate", "task-1", "--workspace", str(tmp_path)])

    assert approved.exit_code == 0, approved.output
    assert "TASK status=approved" in approved.output
    assert applied.exit_code == 0, applied.output
    assert source.read_text(encoding="utf-8") == "VALUE = 2\n"
    assert validated.exit_code == 0, validated.output
    job = queue.get("task-1")
    assert job is not None
    assert job.status == JobStatus.VALIDATED
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["execution_state"] == "validated"
    assert artifact["applied"] is True


def test_task_propose_generates_code_changes_for_existing_proposal(tmp_path: Path) -> None:
    paths = ensure_workspace(tmp_path)
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    queue = SQLiteQueueStore(paths["tasks_db"])
    queue.enqueue(
        Job(
            id="task-1",
            type="demo",
            status=JobStatus.PROPOSAL_READY,
            payload={"task": "Change VALUE to 2 in app.py"},
        )
    )
    (paths["reports"] / "worker-task-1.json").write_text(
        json.dumps({"job_id": "task-1", "execution_state": "proposal_ready"}),
        encoding="utf-8",
    )

    result = propose_task(
        workspace=tmp_path,
        tasks_db=paths["tasks_db"],
        knowledge_db=paths["knowledge_db"],
        reports_dir=paths["reports"],
        job_id="task-1",
        ollama_client=FakeOllamaClient(),  # type: ignore[arg-type]
    )
    artifact = json.loads((paths["reports"] / "worker-task-1.json").read_text(encoding="utf-8"))

    assert result.decision == "proposed"
    assert result.details["changes"] == 1
    assert artifact["code_changes"][0]["file"] == "app.py"
    assert artifact["execution_state"] == "proposal_ready"


def test_task_propose_cli_without_ollama_uses_deterministic_pet_store_fallback(tmp_path: Path) -> None:
    paths = ensure_workspace(tmp_path)
    cart_store = tmp_path / "src" / "store"
    cart_store.mkdir(parents=True)
    (cart_store / "cart.store.ts").write_text(
        "      getSubtotal: () => {\n"
        "        // NOTE: This is for display only. Final price from server.\n"
        "        return 0;\n"
        "      },\n",
        encoding="utf-8",
    )
    SQLiteQueueStore(paths["tasks_db"]).enqueue(
        Job(id="task-1", type="demo", status=JobStatus.PROPOSAL_READY, payload={"task": "patch cart getSubtotal"})
    )
    runner = CliRunner()

    result = runner.invoke(app, ["task", "propose", "task-1", "--no-ollama", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "deterministic code change proposal generated" in result.output
    assert "CHANGES count=1" in result.output


def test_deterministic_propose_denies_unknown_task(tmp_path: Path) -> None:
    paths = ensure_workspace(tmp_path)
    SQLiteQueueStore(paths["tasks_db"]).enqueue(
        Job(id="task-1", type="demo", status=JobStatus.PROPOSAL_READY, payload={"task": "unknown task"})
    )

    result = propose_task_deterministic(
        workspace=tmp_path,
        tasks_db=paths["tasks_db"],
        reports_dir=paths["reports"],
        job_id="task-1",
    )

    assert result.decision == "denied"


def test_task_apply_denies_missing_code_changes(tmp_path: Path) -> None:
    paths = ensure_workspace(tmp_path)
    queue = SQLiteQueueStore(paths["tasks_db"])
    queue.enqueue(Job(id="task-1", type="demo", status=JobStatus.PROPOSAL_READY, payload={"task": "analyze"}))
    (paths["reports"] / "worker-task-1.json").write_text(
        json.dumps({"job_id": "task-1", "execution_state": "proposal_ready"}),
        encoding="utf-8",
    )
    runner = CliRunner()

    approved = runner.invoke(app, ["task", "approve", "task-1", "--workspace", str(tmp_path)])
    applied = runner.invoke(app, ["task", "apply", "task-1", "--workspace", str(tmp_path)])

    assert approved.exit_code == 0, approved.output
    assert applied.exit_code == 1
    assert "artifact has no code_changes" in applied.output
    job = queue.get("task-1")
    assert job is not None
    assert job.status == JobStatus.APPROVED


def test_apply_safety_rejects_ambiguous_snippet_and_generated_paths(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("VALUE = 1\nVALUE = 1\n", encoding="utf-8")
    generated = tmp_path / ".next"
    generated.mkdir()
    (generated / "bundle.js").write_text("VALUE = 1\n", encoding="utf-8")

    ambiguous = validate_code_changes_for_apply(
        tmp_path,
        [
            {
                "file": "app.py",
                "original_snippet": "VALUE = 1\n",
                "new_snippet": "VALUE = 2\n",
            }
        ],
    )
    generated_path = validate_code_changes_for_apply(
        tmp_path,
        [
            {
                "file": ".next/bundle.js",
                "original_snippet": "VALUE = 1\n",
                "new_snippet": "VALUE = 2\n",
            }
        ],
    )

    assert ambiguous.passed is False
    assert "ambiguous" in ambiguous.reason
    assert generated_path.passed is False
    assert "generated/runtime path" in generated_path.reason


def test_apply_safety_rejects_too_many_files(tmp_path: Path) -> None:
    changes = []
    for index in range(4):
        path = tmp_path / f"file{index}.py"
        path.write_text(f"VALUE = {index}\n", encoding="utf-8")
        changes.append(
            {
                "file": f"file{index}.py",
                "original_snippet": f"VALUE = {index}\n",
                "new_snippet": f"VALUE = {index + 10}\n",
            }
        )

    result = validate_code_changes_for_apply(tmp_path, changes)

    assert result.passed is False
    assert "changed files exceed" in result.reason


def test_detect_validation_commands_for_node_and_python(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"lint": "eslint .", "build": "next build"}}),
        encoding="utf-8",
    )
    assert detect_validation_commands(tmp_path) == ["npm run lint", "npm run build"]

    py_project = tmp_path / "py"
    py_project.mkdir()
    (py_project / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    assert detect_validation_commands(py_project) == ["python -m pytest"]


def test_task_validate_auto_runs_detected_commands(tmp_path: Path) -> None:
    paths = ensure_workspace(tmp_path)
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "node -e \"process.exit(0)\""}}),
        encoding="utf-8",
    )
    queue = SQLiteQueueStore(paths["tasks_db"])
    queue.enqueue(Job(id="task-1", type="demo", status=JobStatus.APPROVED, payload={"task": "validate"}))
    (paths["reports"] / "worker-task-1.json").write_text(
        json.dumps({"job_id": "task-1", "execution_state": "approved"}),
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(app, ["task", "validate", "task-1", "--auto", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "CHECK command=\"npm run test\" exit=0" in result.output
    job = queue.get("task-1")
    assert job is not None
    assert job.status == JobStatus.VALIDATED
    artifact = json.loads((paths["reports"] / "worker-task-1.json").read_text(encoding="utf-8"))
    assert artifact["validation_auto_commands"] == ["npm run test"]
