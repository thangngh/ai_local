from __future__ import annotations

import json
from pathlib import Path

from ai_local.benchmark.llm_penalties import _approve_automatically_ok, ollama_pass_criteria_checks
from ai_local.benchmark.models import GoldenTask
from ai_local.benchmark.ollama_eval import evaluate_ollama_response
from ai_local.llm.ollama import OllamaChatResult, TokenUsage


def test_approve_automatically_ok_for_use_with_cited_evidence() -> None:
    task = GoldenTask.model_validate(
        json.loads(Path("golden_tasks/notebooklm_claim_parse/task.json").read_text(encoding="utf-8"))
    )
    content = (
        "DECISION: use\n"
        "EVIDENCE: docs/architecture.md, ai_local/indexer/sqlite_store.py\n"
        "RATIONALE: Strong rank and cited project sources support the FTS5 retrieval claim."
    )
    assert _approve_automatically_ok(task, content, "use") is True
    checks = ollama_pass_criteria_checks(task, content, "use")
    assert checks["approve automatically"] is True


def test_evaluate_ollama_notebooklm_claim_no_forbidden_failure() -> None:
    task = GoldenTask.model_validate(
        json.loads(Path("golden_tasks/notebooklm_claim_parse/task.json").read_text(encoding="utf-8"))
    )
    content = (
        "DECISION: use\n"
        "EVIDENCE: docs/architecture.md, ai_local/indexer/sqlite_store.py\n"
        "RATIONALE: Strong rank and cited project sources support the FTS5 retrieval claim."
    )
    chat = OllamaChatResult(
        model="test",
        content=content,
        latency_ms=1,
        token_usage=TokenUsage(
            input_tokens=1,
            output_tokens=1,
            total_tokens=2,
            input_chars=1,
            output_chars=1,
            token_source="test",
        ),
    )
    outcome = evaluate_ollama_response(task, chat)
    assert "forbidden:approve automatically" not in outcome.failed_criteria
