from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ai_local.cli import app


def test_init_is_idempotent(tmp_path: Path) -> None:
    runner = CliRunner()
    first = runner.invoke(app, ["init", "--workspace", str(tmp_path)])
    second = runner.invoke(app, ["init", "--workspace", str(tmp_path)])
    assert first.exit_code == 0
    assert second.exit_code == 0
    assert (tmp_path / ".ai-local" / "config.yaml").is_file()
    assert (tmp_path / ".ai-local" / "logs").is_dir()
    assert (tmp_path / ".ai-local" / "reports").is_dir()
    assert (tmp_path / ".ai-local" / "backups").is_dir()


def test_demo_run_basic_smoke(tmp_path: Path) -> None:
    runner = CliRunner()
    
    # Run 1
    result1 = runner.invoke(app, ["demo", "run", "basic", "--workspace", str(tmp_path)])
    assert result1.exit_code == 0, result1.output
    
    assert "DEMO basic" in result1.output
    assert "STEP init PASS" in result1.output
    assert "mode=created" in result1.output
    assert "STEP ask PASS" in result1.output
    assert "REPORT" in result1.output
    
    # Run 2
    result2 = runner.invoke(app, ["demo", "run", "basic", "--workspace", str(tmp_path)])
    assert result2.exit_code == 0, result2.output
    assert "mode=reused" in result2.output
    
    report_file = tmp_path / ".ai-local" / "reports" / "demo-basic.json"
    assert report_file.exists()
    
    import json
    report_data = json.loads(report_file.read_text(encoding="utf-8"))
    assert report_data["status"] == "pass"
    assert "steps" in report_data
    assert "artifacts" in report_data
    
    ask_step = next(step for step in report_data["steps"] if step["name"] == "ask")
    assert "decision" in ask_step
    
    knowledge_step = next(step for step in report_data["steps"] if step["name"] == "knowledge_add")
    assert knowledge_step["mode"] == "reused"
    
    search_step = next(step for step in report_data["steps"] if step["name"] == "knowledge_search")
    assert search_step["demo_matches"] == 1
    
    # Check knowledge store directly for duplicates
    from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore
    db_path = tmp_path / ".ai-local" / "knowledge.db"
    store = SQLiteKnowledgeStore(db_path)
    entries = store.list_all()
    demo_notes = [e for e in entries if e.title == "demo:local-first-invariant"]
    assert len(demo_notes) == 1


def test_grouped_demo_cli_surface(tmp_path: Path) -> None:
    runner = CliRunner()
    help_result = runner.invoke(app, ["--help"])
    init_result = runner.invoke(app, ["init", "--workspace", str(tmp_path)])
    show_result = runner.invoke(app, ["config", "show", "--workspace", str(tmp_path)])
    validate_result = runner.invoke(app, ["config", "validate", "--workspace", str(tmp_path)])
    stats_result = runner.invoke(app, ["index", "stats", "--workspace", str(tmp_path)])
    demo_result = runner.invoke(app, ["demo", "run", "basic", "--workspace", str(tmp_path)])
    service_result = runner.invoke(
        app,
        ["service", "install", "--dry-run", "--workspace", str(tmp_path)],
    )

    assert help_result.exit_code == 0, help_result.output
    assert "demo" in help_result.output
    assert init_result.exit_code == 0, init_result.output
    assert show_result.exit_code == 0, show_result.output
    assert validate_result.exit_code == 0, validate_result.output
    assert stats_result.exit_code == 0, stats_result.output
    assert demo_result.exit_code == 0, demo_result.output
    assert service_result.exit_code == 0, service_result.output


def test_ask_command(tmp_path: Path) -> None:
    runner = CliRunner()
    
    # 1. Setup workspace and add knowledge
    runner.invoke(app, ["init", "--workspace", str(tmp_path)])
    add_result = runner.invoke(app, ["knowledge", "add-note", "AI Local keeps workflow state local-first.", "--tag", "invariant", "--workspace", str(tmp_path)])
    assert add_result.exit_code == 0
    
    # 2. Test ask with --show-evidence
    ask_result = runner.invoke(app, ["ask", "What does AI Local keep local?", "--show-evidence", "--workspace", str(tmp_path)])
    assert ask_result.exit_code == 0
    assert "DECISION: enough_context" in ask_result.output
    assert "EVIDENCE:" in ask_result.output
    
    # 3. Check JSON report
    reports_dir = tmp_path / ".ai-local" / "reports"
    reports = list(reports_dir.glob("ask-*.json"))
    assert len(reports) == 1
    
    import json
    report_data = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report_data["decision"] == "enough_context"
    assert report_data["question"] == "What does AI Local keep local?"
    assert len(report_data["evidence"]) > 0
    assert report_data["evidence"][0]["source"] == "knowledge"


def test_ask_low_context(tmp_path: Path) -> None:
    runner = CliRunner()
    
    # Empty workspace
    runner.invoke(app, ["init", "--workspace", str(tmp_path)])
    
    ask_result = runner.invoke(app, ["ask", "completely unknown topic", "--workspace", str(tmp_path)])
    assert ask_result.exit_code == 0
    assert "DECISION: low_context" in ask_result.output
    
    reports_dir = tmp_path / ".ai-local" / "reports"
    reports = list(reports_dir.glob("ask-*.json"))
    assert len(reports) == 1
    
    import json
    report_data = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report_data["decision"] == "low_context"


def test_knowledge_dedup_remove_cleanup_and_stats(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(app, ["init", "--workspace", str(tmp_path)])

    first = runner.invoke(
        app,
        ["knowledge", "add-note", "CartStore validates shopId", "--tag", "cart,validation", "--workspace", str(tmp_path)],
    )
    duplicate = runner.invoke(
        app,
        ["knowledge", "add-note", "CartStore validates shopId  ", "--tag", "cart,validation", "--workspace", str(tmp_path)],
    )
    stats = runner.invoke(app, ["knowledge", "stats", "--workspace", str(tmp_path)])
    remove = runner.invoke(app, ["knowledge", "remove", "1", "--workspace", str(tmp_path)])
    cleanup = runner.invoke(app, ["knowledge", "cleanup", "--dedup", "--workspace", str(tmp_path)])

    assert first.exit_code == 0, first.output
    assert duplicate.exit_code != 0, duplicate.output
    assert "KNOWLEDGE note rejected" in duplicate.output
    assert stats.exit_code == 0, stats.output
    assert "notes=1" in stats.output
    assert remove.exit_code == 0, remove.output
    assert cleanup.exit_code == 0, cleanup.output


def test_ask_prefers_relevant_note_over_readme_file(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(app, ["init", "--workspace", str(tmp_path)])
    runner.invoke(
        app,
        ["knowledge", "add-note", "This is a Next.js project bootstrapped with create-next-app.", "--tag", "readme", "--workspace", str(tmp_path)],
    )
    runner.invoke(
        app,
        ["knowledge", "add-note", "CartStore getSubtotal is display-only; final price must come from server.", "--tag", "cart,price,bug", "--workspace", str(tmp_path)],
    )

    result = runner.invoke(
        app,
        ["ask", "Why is CartStore getSubtotal display-only?", "--workspace", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "CartStore getSubtotal" in result.output
    assert "create-next-app" not in result.output


def test_demo_run_pet_store_offline_happy_path(tmp_path: Path) -> None:
    runner = CliRunner()
    cart_store = tmp_path / "src" / "store"
    cart_store.mkdir(parents=True)
    (cart_store / "cart.store.ts").write_text(
        "      getSubtotal: () => {\n"
        "        // NOTE: This is for display only. Final price from server.\n"
        "        return 0;\n"
        "      },\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["demo", "run", "pet-store", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "DEMO pet-store" in result.output
    assert "STEP propose PROPOSED" in result.output
    assert "STEP apply APPLIED" in result.output
    assert "STEP validate VALIDATED" in result.output
    assert (tmp_path / ".ai-local" / "reports" / "demo-pet-store.json").is_file()
    content = (cart_store / "cart.store.ts").read_text(encoding="utf-8")
    assert "display-only estimate" in content
