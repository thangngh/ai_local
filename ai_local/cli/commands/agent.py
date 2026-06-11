"""Agent commands for the ai-local CLI.

Provides a complete agent workflow:
1. plan  — plan from a goal
2. run   — plan + retrieve context + execute plan steps
3. ask   — ask a question using agent context engine (enhanced)
4. loop  — interactive agent loop with tool use
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from ai_local.config.workspace import ensure_workspace, get_ollama_config
from ai_local.llm.ollama import OllamaClient, OllamaConfig, OllamaError

agent_app = typer.Typer()


# ── Agent Engine ──────────────────────────────────────────────────────────


def _search_knowledge(db_path: Path, query: str) -> list[dict[str, Any]]:
    """Search the knowledge store for relevant context."""
    import sqlite3

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        words = [w.strip("?.,!;:") for w in query.split() if len(w) > 2]
        if not words:
            conn.close()
            return []
        conditions = []
        params = []
        for w in words:
            p = f"%{w}%"
            conditions.append("(title LIKE ? OR content LIKE ? OR tags_json LIKE ?)")
            params.extend([p, p, p])
        sql = f"SELECT * FROM knowledge WHERE {' OR '.join(conditions)} ORDER BY id"
        rows = conn.execute(sql, tuple(params)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _search_index(db_path: Path, query: str) -> list[dict[str, Any]]:
    """Search the project index for relevant code chunks."""
    try:
        from ai_local.indexer.sqlite_store import KnowledgeIndexStore

        store = KnowledgeIndexStore(db_path)
        store.initialize()
        hits = store.search_chunks(query, limit=10)
        return [
            {"source_ref": h.source_ref, "file_path": h.file_path, "content": h.content[:300]}
            for h in hits
        ]
    except Exception:
        return []


def _read_file(file_path: Path, workspace: Path) -> dict[str, Any]:
    """Read a file from the workspace and return its content + metadata."""
    abs_path = workspace / file_path if not file_path.is_absolute() else file_path
    if not abs_path.exists():
        return {"error": f"File not found: {file_path}"}
    if abs_path.is_dir():
        return {"error": f"Path is a directory: {file_path}"}
    try:
        content = abs_path.read_text(encoding="utf-8")
        return {
            "path": str(file_path),
            "size": len(content),
            "lines": content.count("\n") + 1,
            "content": content,
        }
    except Exception as exc:
        return {"error": f"Cannot read {file_path}: {exc}"}


def _write_file(file_path: Path, content: str, workspace: Path) -> dict[str, Any]:
    """Write content to a file in the workspace."""
    abs_path = workspace / file_path if not file_path.is_absolute() else file_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(content, encoding="utf-8")
    return {"path": str(file_path), "size": len(content), "status": "written"}


def _list_files(workspace: Path, pattern: str | None = None) -> list[str]:
    """List project files, optionally filtered by pattern."""
    from ai_local.indexer.scanner import scan_files

    root = workspace
    try:
        paths = scan_files(root)
        result = [str(p.relative_to(root)) for p in paths]
        if pattern:
            result = [p for p in result if pattern.lower() in p.lower()]
        return result[:50]  # cap at 50
    except Exception:
        return []


# ── Tool Execution Engine ─────────────────────────────────────────────────


_TOOL_REGISTRY: dict[str, Any] = {
    "search_knowledge": _search_knowledge,
    "search_index": _search_index,
    "read_file": _read_file,
    "write_file": _write_file,
    "list_files": _list_files,
}


def _execute_tool(
    tool_name: str,
    kwargs: dict[str, Any],
    db_path: Path,
    workspace: Path,
) -> dict[str, Any]:
    """Execute a tool by name with validated kwargs."""
    tool = _TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return {"error": f"Unknown tool: {tool_name}"}

    # Inject context kwargs
    if tool_name == "search_knowledge" or tool_name == "search_index":
        kwargs["db_path"] = db_path
    if tool_name in ("read_file", "write_file", "list_files"):
        kwargs["workspace"] = workspace

    try:
        result = tool(**kwargs)
        return {"tool": tool_name, "result": result}
    except Exception as exc:
        return {"tool": tool_name, "error": str(exc)}


# ── Ollama Integration ────────────────────────────────────────────────────


def _get_ollama_client(
    use_ollama: bool | None = None,
    model: str | None = None,
    base_url: str | None = None,
    workspace: Path | None = None,
) -> OllamaClient | None:
    """Create Ollama client if available and requested.

    Falls back to workspace config defaults when ``model`` or ``base_url``
    are not explicitly provided.

    * ``use_ollama=True``  -- require Ollama; raises if unreachable
    * ``use_ollama=None``  -- auto-detect; returns None if unreachable
    * ``use_ollama=False`` -- skip
    """
    if use_ollama is False:
        return None

    # Load defaults from workspace config
    ws_model = model
    ws_base_url = base_url
    if workspace is not None:
        ol_config = get_ollama_config(workspace)
        if ws_model is None:
            ws_model = ol_config.get("model", "qwen2.5:0.5b")
        if ws_base_url is None:
            ws_base_url = ol_config.get("base_url", "http://127.0.0.1:11434")
        # If config says explicitly enabled, treat None as True
        if use_ollama is None and ol_config.get("enabled", False) is True:
            use_ollama = True

    resolved_model = ws_model or "qwen2.5:0.5b"
    resolved_url = ws_base_url or "http://127.0.0.1:11434"

    config = OllamaConfig(base_url=resolved_url, model=resolved_model)
    client = OllamaClient(config)
    try:
        ok = client.health_check()
        if not ok:
            msg = "Ollama server unreachable"
            if use_ollama is True:
                raise ConnectionError(msg)
            return None
        client.ensure_model()
    except (OllamaError, ConnectionError) as exc:
        if use_ollama is True:
            raise
        return None

    return client


def _llm_plan(
    client: OllamaClient,
    goal: str,
    knowledge_context: list[dict[str, Any]],
    index_context: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Use LLM to generate a plan from goal + context."""
    context_summary: dict[str, Any] = {
        "goal": goal,
        "knowledge_notes": [
            {"title": k.get("title", "?"), "content": k.get("content", "")[:200]}
            for k in knowledge_context[:5]
        ],
        "index_files": [
            {"file": i.get("file_path", "?"), "snippet": i.get("content", "")[:200]}
            for i in index_context[:5]
        ],
    }

    system = (
        "You are a code analysis agent. Given a user goal and project context, "
        "return a JSON array of plan steps. Each step must have keys: "
        '"step" (int), "action" (str), "detail" (str). '
        "Return ONLY valid JSON, no markdown, no explanation."
    )
    user = json.dumps(context_summary, indent=2)

    try:
        result = client.chat(system=system, user=user)
        raw = result.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        plan = json.loads(raw)
        if isinstance(plan, list):
            return plan
        raise ValueError("LLM did not return a list")
    except Exception:
        # Fallback: return deterministic plan
        return _deterministic_plan(goal, knowledge_context, index_context)


def _deterministic_plan(
    goal: str,
    knowledge_context: list[dict[str, Any]],
    index_context: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Original deterministic plan logic extracted from _agent_run."""
    plan_items = []
    if knowledge_context:
        plan_items.append({
            "step": 1,
            "action": "Review existing knowledge",
            "detail": f"{len(knowledge_context)} relevant notes found",
        })
    if index_context:
        files = set(ih.get("file_path", "") for ih in index_context if ih.get("file_path"))
        plan_items.append({
            "step": len(plan_items) + 1,
            "action": "Read relevant source files",
            "detail": f"{len(files)} files to read: {', '.join(sorted(files)[:5])}",
        })
    plan_items.append({
        "step": len(plan_items) + 1,
        "action": "Analyze and understand the problem",
        "detail": goal,
    })
    plan_items.append({
        "step": len(plan_items) + 1,
        "action": "Report findings",
        "detail": "Write artifact and optionally update knowledge",
    })
    return plan_items


def _llm_synthesize(
    client: OllamaClient,
    goal: str,
    knowledge_context: list[dict[str, Any]],
    index_context: list[dict[str, Any]],
    tool_uses: list[dict[str, Any]],
) -> str:
    """Use LLM to synthesize a human-readable answer from gathered context."""
    context: dict[str, Any] = {
        "goal": goal,
        "knowledge": [
            {"title": k.get("title", "?"), "content": k.get("content", "")[:500]}
            for k in knowledge_context[:5]
        ],
        "index_hits": [
            {"file": i.get("file_path", "?"), "content": i.get("content", "")[:300]}
            for i in index_context[:5]
        ],
        "files_read": [
            {"file": tu.get("file", "?"), "preview": tu.get("content_preview", "")[:300]}
            for tu in tool_uses if tu.get("tool") == "read_file"
        ],
    }

    system = (
        "You are a senior software engineer reviewing a codebase. "
        "Answer the user's question based on the provided context. "
        "Be specific, reference actual code and files. "
        "If the context is insufficient, say so."
    )
    user = json.dumps(context, indent=2)

    try:
        result = client.chat(system=system, user=user)
        return result.content.strip()
    except Exception:
        return _synthesize_answer(goal, knowledge_context, index_context, tool_uses)


def _llm_ask(
    client: OllamaClient,
    query: str,
    knowledge_context: list[dict[str, Any]],
    index_context: list[dict[str, Any]],
) -> str:
    """Use LLM to answer a direct question with context."""
    context: dict[str, Any] = {
        "question": query,
        "knowledge": [
            {"title": k.get("title", "?"), "content": k.get("content", "")[:500]}
            for k in knowledge_context[:5]
        ],
        "code_context": [
            {"file": i.get("file_path", "?"), "content": i.get("content", "")[:300]}
            for i in index_context[:5]
        ],
    }

    system = (
        "You are a helpful coding assistant. Answer the question using only "
        "the provided knowledge notes and code context. Be concise and specific. "
        "If you don't know, say so."
    )
    user = json.dumps(context, indent=2)

    try:
        result = client.chat(system=system, user=user)
        return result.content.strip()
    except Exception:
        return ""


# ── Agent run ─────────────────────────────────────────────────────────────


def _agent_run(
    goal: str,
    workspace: Path,
    knowledge_db: Path,
    *,
    max_steps: int = 8,
    verbose: bool = False,
    ollama_client: OllamaClient | None = None,
) -> dict[str, Any]:
    """Execute a full agent run: plan -> retrieve -> execute -> report.

    The agent loop:
    1. Understand goal (extract entities, keywords)
    2. Gather context (knowledge + index search)
    3. Plan steps (list of actions to take) -- uses LLM if client provided
    4. Execute each step using tool registry
    5. Synthesize findings -- uses LLM if client provided
    6. Generate report
    """
    steps: list[dict[str, Any]] = []
    start_time = time.time()

    # Step 1: Extract entities and keywords from goal
    entities = set(re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", goal))
    keywords = [w.lower().strip("?.,!;:") for w in goal.split() if len(w) > 3]
    steps.append({
        "step": "extract",
        "entities": sorted(entities),
        "keywords": keywords,
        "status": "done",
    })

    # Step 2: Gather context (knowledge + index)
    knowledge_hits = _search_knowledge(knowledge_db, goal)
    index_hits = _search_index(knowledge_db, goal)

    # Filter: prefer knowledge.hits with relevant tags
    relevant_knowledge = []
    for kh in knowledge_hits:
        tags = kh.get("tags_json", "")
        if any(kw in (kh.get("title", "") + tags + kh.get("content", "")).lower() for kw in keywords):
            relevant_knowledge.append(kh)

    relevant_index = []
    for ih in index_hits:
        content = (ih.get("file_path", "") + " " + ih.get("content", "")).lower()
        if any(kw in content for kw in keywords):
            relevant_index.append(ih)

    steps.append({
        "step": "retrieve",
        "knowledge_hits": len(knowledge_hits),
        "relevant_knowledge": len(relevant_knowledge),
        "index_hits": len(index_hits),
        "relevant_index": len(relevant_index),
        "status": "done",
    })

    # Step 3: Plan (LLM or deterministic)
    tool_uses = []

    plan_items: list[dict[str, Any]]
    if ollama_client is not None:
        plan_items = _llm_plan(ollama_client, goal, relevant_knowledge, relevant_index)
    else:
        plan_items = _deterministic_plan(goal, relevant_knowledge, relevant_index)

    # Execute plan items (read files from index hits for context)
    read_files = set()
    for ih in relevant_index:
        fp = ih.get("file_path", "")
        if fp and fp not in read_files:
            read_files.add(fp)
            file_data = _read_file(Path(fp), workspace)
            if "error" not in file_data:
                tool_uses.append({
                    "tool": "read_file",
                    "file": fp,
                    "content_preview": file_data["content"][:500],
                })
            if len(tool_uses) > max_steps:
                break

    # If no context found, list project files
    if not relevant_knowledge and not relevant_index:
        files = _list_files(workspace)
        tool_uses.append({
            "tool": "list_files",
            "description": "Listed project files for context",
            "count": len(files),
            "files": files[:20],
        })

    steps.append({
        "step": "plan",
        "tool_uses": len(tool_uses),
        "plan_items": [
            {"tool": tu.get("tool", "analyze"), "target": tu.get("file", tu.get("description", ""))}
            for tu in tool_uses
        ],
        "llm_generated": ollama_client is not None,
        "status": "done",
    })

    # Step 4: Synthesize findings
    findings = []
    for kh in relevant_knowledge[:5]:
        findings.append({
            "source": "knowledge",
            "type": "note" if kh.get("kind") == "note" else "file",
            "id": kh.get("id"),
            "title": kh.get("title"),
            "snippet": kh.get("content", "")[:200],
        })

    for ih in relevant_index[:5]:
        findings.append({
            "source": "index",
            "file": ih.get("file_path"),
            "snippet": ih.get("content", "")[:200],
        })

    # Step 5: Generate answer / analysis (LLM or deterministic)
    elapsed = time.time() - start_time

    if ollama_client is not None:
        answer = _llm_synthesize(ollama_client, goal, relevant_knowledge, relevant_index, tool_uses)
    else:
        answer = _synthesize_answer(goal, relevant_knowledge, relevant_index, tool_uses)

    steps.append({
        "step": "synthesize",
        "findings": findings,
        "answer": answer,
        "tool_uses_detail": tool_uses,
        "llm_generated": ollama_client is not None,
        "status": "done",
    })

    return {
        "goal": goal,
        "elapsed_seconds": round(elapsed, 2),
        "steps": steps,
        "total_tool_uses": len(tool_uses),
        "summary": {
            "knowledge_context": len(relevant_knowledge),
            "index_context": len(relevant_index),
            "files_read": len(read_files),
            "llm_used": ollama_client is not None,
        },
    }


def _synthesize_answer(
    goal: str,
    knowledge_hits: list[dict[str, Any]],
    index_hits: list[dict[str, Any]],
    tool_uses: list[dict[str, Any]],
) -> str:
    """Synthesize a human-readable answer from gathered context."""
    parts = [f"## Agent Analysis: {goal}\n"]
    read_files_list: list[dict[str, Any]] = []

    if knowledge_hits:
        parts.append("### Knowledge Context")
        for kh in knowledge_hits[:3]:
            kind = kh.get("kind", "?")
            title = kh.get("title", "?")
            content = kh.get("content", "")[:300]
            parts.append(f"- [{kind}] **{title}**: {content}")

    if index_hits:
        parts.append("\n### Code Context")
        for ih in index_hits[:5]:
            fp = ih.get("file_path", "?")
            content = ih.get("content", "")[:200]
            parts.append(f"- **{fp}**: {content}")

    read_files_list = [tu for tu in tool_uses if tu.get("tool") == "read_file"]
    if read_files_list:
        parts.append("\n### Files Read")
        for rf in read_files_list[:5]:
            parts.append(f"- {rf.get('file', '?')} (content preview available)")

    parts.append("\n### Result")
    context_summary = (
        f"Found {len(knowledge_hits)} knowledge entries, {len(index_hits)} index hits, "
        f"read {len(read_files_list)} files."
    )
    parts.append(context_summary)
    return "\n".join(parts)


# ── CLI Commands ──────────────────────────────────────────────────────────


@agent_app.command("run")
def agent_run_cmd(
    goal: str = typer.Argument(..., help="The goal / task for the agent"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    verbose: bool = typer.Option(False, "--verbose"),
    output: Path | None = typer.Option(None, "--output", "-o"),
    use_ollama: bool | None = typer.Option(None, "--use-ollama/--no-ollama",
        help="Use Ollama LLM (auto-detect if not specified)"),
    ollama_model: str = typer.Option("qwen2.5:0.5b", "--ollama-model",
        help="Ollama model name"),
    ollama_base_url: str = typer.Option("http://127.0.0.1:11434", "--ollama-base-url",
        help="Ollama server base URL"),
) -> None:
    """Run the agent: plan -> retrieve -> execute -> report.

    Example:
        ai-local agent run "Fix bug in CartStore getSubtotal()"
        ai-local agent run "Explain how auth store works" --verbose
        ai-local agent run "Find all places that use product.price" -o report.json
        ai-local agent run "How does CartStore work?" --use-ollama
    """
    paths = ensure_workspace(workspace)
    typer.echo(f"[Agent] run: {goal}")
    typer.echo(f"   workspace: {workspace}")

    ollama_client = _get_ollama_client(use_ollama, model=ollama_model, base_url=ollama_base_url, workspace=workspace)
    if ollama_client:
        typer.echo(f"   using LLM: {ollama_model or ollama_client.model}")
    else:
        typer.echo("   using deterministic engine (no LLM)")

    result = _agent_run(
        goal,
        workspace,
        paths["knowledge_db"],
        verbose=verbose,
        ollama_client=ollama_client,
    )

    # Print report
    for step in result["steps"]:
        step_name = step["step"]
        step_status = step.get("status", "?")
        icon = "[OK]" if step_status == "done" else "[FAIL]"
        typer.echo(f"\n{icon} Step: {step_name}")
        if step_name == "extract":
            typer.echo(f"   entities: {', '.join(step.get('entities', [])[:10])}")
        elif step_name == "retrieve":
            typer.echo(f"   knowledge: {step.get('relevant_knowledge', 0)} relevant / {step.get('knowledge_hits', 0)} total")
            typer.echo(f"   index: {step.get('relevant_index', 0)} relevant / {step.get('index_hits', 0)} total")
        elif step_name == "plan":
            for item in step.get("plan_items", [])[:5]:
                typer.echo(f"   -> {item.get('tool')}: {item.get('target', '')}")
        elif step_name == "synthesize":
            if verbose or ollama_client:
                typer.echo(f"\n{step.get('answer', '')}")
            for f in step.get("findings", [])[:3]:
                src = f.get("source", "?")
                title = f.get("title", f.get("file", "?"))
                typer.echo(f"   [{src}] {title}")

    typer.echo(f"\n[Elapsed] {result['elapsed_seconds']}s")
    typer.echo(f"[Summary] {result['summary']}")

    # Write report
    if output is None:
        timestamp = int(time.time())
        output = paths["reports"] / f"agent-{timestamp}.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    typer.echo(f"[Report] {output}")


@agent_app.command("plan")
def agent_plan_cmd(
    goal: str = typer.Argument(..., help="The goal to plan for"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    use_ollama: bool | None = typer.Option(None, "--use-ollama/--no-ollama",
        help="Use Ollama LLM (auto-detect if not specified)"),
    ollama_model: str = typer.Option("qwen2.5:0.5b", "--ollama-model"),
    ollama_base_url: str = typer.Option("http://127.0.0.1:11434", "--ollama-base-url"),
) -> None:
    """Plan steps needed to achieve a goal (without executing).

    Example:
        ai-local agent plan "Add discount logic to CartStore"
        ai-local agent plan "Fix all lint errors"
    """
    paths = ensure_workspace(workspace)
    ollama_client = _get_ollama_client(use_ollama, model=ollama_model, base_url=ollama_base_url, workspace=workspace)

    # Gather context
    knowledge_hits = _search_knowledge(paths["knowledge_db"], goal)
    index_hits = _search_index(paths["knowledge_db"], goal)

    typer.echo(f"[Plan] for: {goal}")
    typer.echo(f"   Context: {len(knowledge_hits)} knowledge, {len(index_hits)} index hits\n")

    if ollama_client:
        plan_items = _llm_plan(ollama_client, goal, knowledge_hits, index_hits)
        for item in plan_items:
            step_num = item.get("step", "?")
            action = item.get("action", "?")
            detail = item.get("detail", "")
            typer.echo(f"  Step {step_num}: {action}")
            typer.echo(f"    {detail}")
    else:
        # Generate deterministic plan items
        plan_items = []
        if knowledge_hits:
            plan_items.append({
                "step": 1,
                "action": "Review existing knowledge",
                "detail": f"{len(knowledge_hits)} relevant notes found",
            })
        if index_hits:
            files = set(ih.get("file_path", "") for ih in index_hits if ih.get("file_path"))
            plan_items.append({
                "step": len(plan_items) + 1,
                "action": "Read relevant source files",
                "detail": f"{len(files)} files to read: {', '.join(sorted(files)[:5])}",
            })
        plan_items.append({
            "step": len(plan_items) + 1,
            "action": "Analyze and understand the problem",
            "detail": goal,
        })
        plan_items.append({
            "step": len(plan_items) + 1,
            "action": "Implement changes",
            "detail": "Modify source files based on analysis",
        })
        plan_items.append({
            "step": len(plan_items) + 1,
            "action": "Validate changes",
            "detail": "Run tests or gates",
        })
        plan_items.append({
            "step": len(plan_items) + 1,
            "action": "Report findings",
            "detail": "Write artifact and optionally update knowledge",
        })

        for item in plan_items:
            step_num = item.get("step", "?")
            action = item.get("action", "?")
            detail = item.get("detail", "")
            typer.echo(f"  Step {step_num}: {action}")
            typer.echo(f"    {detail}")


@agent_app.command("ask")
def agent_ask_cmd(
    query: str = typer.Argument(..., help="The question to ask"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    show_context: bool = typer.Option(False, "--show-context"),
    use_ollama: bool | None = typer.Option(None, "--use-ollama/--no-ollama",
        help="Use Ollama LLM (auto-detect if not specified)"),
    ollama_model: str = typer.Option("qwen2.5:0.5b", "--ollama-model"),
    ollama_base_url: str = typer.Option("http://127.0.0.1:11434", "--ollama-base-url"),
) -> None:
    """Ask a question using the agent context engine.

    Enhanced version of `ai-local ask` that uses agent's
    knowledge + index + code reading for better answers.

    Example:
        ai-local agent ask "How does CartStore validate shopId?"
        ai-local agent ask "Find all bugs in price calculation"
    """
    paths = ensure_workspace(workspace)
    ollama_client = _get_ollama_client(use_ollama, model=ollama_model, base_url=ollama_base_url, workspace=workspace)

    # Run agent (with fewer steps for Q&A mode)
    result = _agent_run(query, workspace, paths["knowledge_db"],
                        max_steps=5, ollama_client=ollama_client)

    # Extract answer from steps
    synthesize_step = next((s for s in result["steps"] if s["step"] == "synthesize"), None)
    if synthesize_step and synthesize_step.get("answer"):
        typer.echo(synthesize_step["answer"])
    else:
        # Fallback to simple search
        typer.echo("(Falling back to standard ask...)")
        typer.echo(f"DECISION: enough_context")
        typer.echo(f"QUESTION: {query}")

        knowledge_hits = _search_knowledge(paths["knowledge_db"], query)
        index_hits = _search_index(paths["knowledge_db"], query)

        for kh in knowledge_hits[:5]:
            typer.echo(f"EVIDENCE: knowledge_id={kh.get('id')} title={kh.get('title', '?')}")
        for ih in index_hits[:3]:
            typer.echo(f"EVIDENCE: {ih.get('file_path', '?')}")

        typer.echo(f"\nREPORT: {paths['reports'] / 'agent-ask-latest.json'}")

    if show_context:
        typer.echo(f"\n[Context] {result['summary']}")


@agent_app.command("status")
def agent_status_cmd(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """Show agent engine status and available context.

    Example:
        ai-local agent status
    """
    paths = ensure_workspace(workspace)

    # Knowledge stats
    import sqlite3

    try:
        conn = sqlite3.connect(str(paths["knowledge_db"]))
        row = conn.execute("SELECT COUNT(*) as c, kind FROM knowledge GROUP BY kind").fetchall()
        note_count = sum(r[0] for r in row if r[1] == "note")
        file_count = sum(r[0] for r in row if r[1] == "file")
        conn.close()
    except Exception:
        note_count = file_count = 0

    # Index stats
    try:
        from ai_local.indexer.sqlite_store import KnowledgeIndexStore

        store = KnowledgeIndexStore(paths["knowledge_db"])
        store.initialize()
        stats = store.stats()
        index_files = stats.files
        index_chunks = stats.chunks
    except Exception:
        index_files = index_chunks = 0

    # Tool registry
    available_tools = sorted(_TOOL_REGISTRY.keys())

    typer.echo("[Agent] Engine Status")
    typer.echo(f"  workspace: {workspace}")
    typer.echo(f"  knowledge.db: {workspace / '.ai-local' / 'knowledge.db'}")
    typer.echo("")
    typer.echo("[Knowledge Store]:")
    typer.echo(f"  Notes: {note_count}")
    typer.echo(f"  Files: {file_count}")
    typer.echo("")
    typer.echo("[Index Store]:")
    typer.echo(f"  Files: {index_files}")
    typer.echo(f"  Chunks: {index_chunks}")
    typer.echo("")
    typer.echo("[Available Tools]:")
    for tool in available_tools:
        typer.echo(f"  - {tool}")
