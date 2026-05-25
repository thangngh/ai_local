from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ai_local.audit.store import AuditEvent


@dataclass(frozen=True)
class PipelineAuditChainSummary:
    chain_id: str
    scenario: str
    status: str
    final_state: str
    evidence_count: int
    audit_event_count: int


class PipelineAuditChainStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS phase9_pipeline_runs (
                    chain_id TEXT PRIMARY KEY,
                    scenario TEXT NOT NULL,
                    status TEXT NOT NULL,
                    final_state TEXT NOT NULL,
                    output_ready INTEGER NOT NULL,
                    hop_depth INTEGER NOT NULL,
                    noise_profile TEXT NOT NULL,
                    conflict_profile TEXT NOT NULL,
                    plan_decision TEXT,
                    skill_decision TEXT,
                    patch_decision TEXT,
                    created_at TEXT NOT NULL,
                    report_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS phase9_pipeline_stages (
                    chain_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    PRIMARY KEY (chain_id, ordinal),
                    FOREIGN KEY (chain_id) REFERENCES phase9_pipeline_runs(chain_id)
                );
                CREATE TABLE IF NOT EXISTS phase9_pipeline_evidence_refs (
                    chain_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    evidence_ref TEXT NOT NULL,
                    PRIMARY KEY (chain_id, ordinal),
                    FOREIGN KEY (chain_id) REFERENCES phase9_pipeline_runs(chain_id)
                );
                CREATE TABLE IF NOT EXISTS phase9_pipeline_risk_flags (
                    chain_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    risk_flag TEXT NOT NULL,
                    PRIMARY KEY (chain_id, ordinal),
                    FOREIGN KEY (chain_id) REFERENCES phase9_pipeline_runs(chain_id)
                );
                CREATE TABLE IF NOT EXISTS phase9_pipeline_reasons (
                    chain_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    PRIMARY KEY (chain_id, ordinal),
                    FOREIGN KEY (chain_id) REFERENCES phase9_pipeline_runs(chain_id)
                );
                CREATE TABLE IF NOT EXISTS phase9_pipeline_audit_events (
                    chain_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT NOT NULL,
                    result TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (chain_id, ordinal),
                    FOREIGN KEY (chain_id) REFERENCES phase9_pipeline_runs(chain_id)
                );
                """
            )

    def persist(
        self,
        report: dict[str, object],
        audit_events: list[AuditEvent],
        *,
        chain_id: str | None = None,
    ) -> str:
        self.initialize()
        chain_id = chain_id or str(uuid4())
        report_with_chain = {**report, "chain_id": chain_id}
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO phase9_pipeline_runs(
                    chain_id, scenario, status, final_state, output_ready,
                    hop_depth, noise_profile, conflict_profile, plan_decision,
                    skill_decision, patch_decision, created_at, report_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chain_id,
                    str(report["scenario"]),
                    str(report["status"]),
                    str(report["final_state"]),
                    1 if bool(report["output_ready"]) else 0,
                    _int_value(report["hop_depth"]),
                    str(report["noise_profile"]),
                    str(report["conflict_profile"]),
                    _nullable(report.get("plan_decision")),
                    _nullable(report.get("skill_decision")),
                    _nullable(report.get("patch_decision")),
                    datetime.now(UTC).isoformat(),
                    json.dumps(report_with_chain, sort_keys=True),
                ),
            )
            _insert_ordered(
                connection,
                "phase9_pipeline_stages",
                "stage",
                chain_id,
                _string_list(report["stages"]),
            )
            _insert_ordered(
                connection,
                "phase9_pipeline_evidence_refs",
                "evidence_ref",
                chain_id,
                _string_list(report["evidence_refs"]),
            )
            _insert_ordered(
                connection,
                "phase9_pipeline_risk_flags",
                "risk_flag",
                chain_id,
                _string_list(report["risk_flags"]),
            )
            _insert_ordered(
                connection,
                "phase9_pipeline_reasons",
                "reason",
                chain_id,
                _string_list(report["reasons"]),
            )
            connection.executemany(
                """
                INSERT INTO phase9_pipeline_audit_events(
                    chain_id, ordinal, action, target, result, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chain_id,
                        index,
                        event.action,
                        event.target,
                        event.result,
                        event.created_at,
                    )
                    for index, event in enumerate(audit_events)
                ],
            )
        return chain_id

    def list_summaries(self) -> list[PipelineAuditChainSummary]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    run.chain_id,
                    run.scenario,
                    run.status,
                    run.final_state,
                    COUNT(DISTINCT evidence.ordinal) AS evidence_count,
                    COUNT(DISTINCT audit.ordinal) AS audit_event_count
                FROM phase9_pipeline_runs AS run
                LEFT JOIN phase9_pipeline_evidence_refs AS evidence
                    ON evidence.chain_id = run.chain_id
                LEFT JOIN phase9_pipeline_audit_events AS audit
                    ON audit.chain_id = run.chain_id
                GROUP BY run.chain_id
                ORDER BY run.created_at DESC
                """
            ).fetchall()
        return [
            PipelineAuditChainSummary(
                chain_id=str(row["chain_id"]),
                scenario=str(row["scenario"]),
                status=str(row["status"]),
                final_state=str(row["final_state"]),
                evidence_count=int(row["evidence_count"]),
                audit_event_count=int(row["audit_event_count"]),
            )
            for row in rows
        ]

    def read_report(self, chain_id: str) -> dict[str, object] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT report_json FROM phase9_pipeline_runs WHERE chain_id = ?",
                (chain_id,),
            ).fetchone()
        if row is None:
            return None
        loaded = json.loads(str(row["report_json"]))
        if not isinstance(loaded, dict):
            return None
        return loaded

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection


def _insert_ordered(
    connection: sqlite3.Connection,
    table: str,
    value_column: str,
    chain_id: str,
    values: list[str],
) -> None:
    connection.executemany(
        f"INSERT INTO {table}(chain_id, ordinal, {value_column}) VALUES (?, ?, ?)",
        [(chain_id, index, value) for index, value in enumerate(values)],
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _nullable(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    msg = f"Expected int-like value, got {type(value).__name__}"
    raise TypeError(msg)
