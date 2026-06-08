import json
import time
from pathlib import Path

import typer

from ai_local.indexer.sqlite_store import KnowledgeIndexStore
from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore


def ask_group(
    query: str = typer.Argument(...),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    show_evidence: bool = typer.Option(False, "--show-evidence"),
) -> None:
    # Need to import _ensure_workspace here to avoid circular imports
    from ai_local.cli.app import _ensure_workspace

    paths = _ensure_workspace(workspace)

    # 1. Search durable knowledge store
    store = SQLiteKnowledgeStore(paths["knowledge_db"])
    store.initialize()
    knowledge_hits = store.search(query)

    # 2. Search project index
    index_store = KnowledgeIndexStore(paths["knowledge_db"])
    try:
        index_store.initialize()
        index_hits = index_store.search_chunks(query, limit=5)
    except Exception:
        index_hits = []

    # 3. Decision
    if not knowledge_hits and not index_hits:
        decision = "low_context"
        answer_draft = ""
    else:
        decision = "enough_context"
        # Just use the first piece of evidence as deterministic answer draft
        if knowledge_hits:
            answer_draft = f"Based on knowledge note: {knowledge_hits[0].content}"
        else:
            answer_draft = f"Based on index: {index_hits[0].content[:100]}"

    # 4. Print
    typer.echo(f"DECISION: {decision}")
    typer.echo(f"QUESTION: {query}")
    if answer_draft:
        typer.echo("ANSWER_DRAFT:")
        typer.echo(answer_draft)

    evidence_list = []

    for hit in knowledge_hits:
        evidence_list.append(
            {
                "source": "knowledge",
                "id": str(hit.id),
                "title": hit.title,
                "score": 1.0,
                "snippet": hit.content[:100],
            }
        )
        if show_evidence:
            typer.echo(f"EVIDENCE: knowledge_id={hit.id} title={hit.title}")

    for hit in index_hits:
        evidence_list.append(
            {
                "source": "index",
                "id": hit.source_ref,
                "title": hit.file_path,
                "score": 1.0,
                "snippet": hit.content[:100],
            }
        )
        if show_evidence:
            typer.echo(f"EVIDENCE: {hit.source_ref}")

    # 5. Write report
    report = {
        "question": query,
        "decision": decision,
        "answer_draft": answer_draft,
        "evidence": evidence_list,
    }

    timestamp = int(time.time())
    report_path = paths["reports"] / f"ask-{timestamp}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    typer.echo(f"REPORT: {report_path}")
