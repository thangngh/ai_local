import json
import sqlite3
from pathlib import Path

from ai_local.agent.state import AgentRun, AgentRunStatus
from ai_local.db.schema import list_schema_versions, migrate_component
from ai_local.planner.models import PlanItem


class InMemoryAgentRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, AgentRun] = {}

    def create(self, run: AgentRun) -> AgentRun:
        self._runs[run.id] = run
        return run

    def get(self, run_id: str) -> AgentRun | None:
        return self._runs.get(run_id)

    def mark_planned(self, run_id: str, plan: list[PlanItem]) -> AgentRun:
        run = self._runs[run_id]
        run.plan = list(plan)
        run.status = AgentRunStatus.PLANNED
        run.decision = "continue"
        run.next_state = "RETRIEVE"
        return run

    def mark_waiting_user(self, run_id: str, plan: list[PlanItem]) -> AgentRun:
        run = self._runs[run_id]
        run.plan = list(plan)
        run.status = AgentRunStatus.WAITING_USER
        run.decision = "ask_user"
        run.next_state = "ASK_USER"
        return run

    def mark_stopped(self, run_id: str, plan: list[PlanItem]) -> AgentRun:
        run = self._runs[run_id]
        run.plan = list(plan)
        run.status = AgentRunStatus.STOPPED
        run.decision = "stop"
        run.next_state = "STOP"
        return run

    def mark_running(self, run_id: str, *, decision: str, next_state: str) -> AgentRun:
        run = self._runs[run_id]
        run.status = AgentRunStatus.RUNNING
        run.decision = decision
        run.next_state = next_state
        return run

    def mark_succeeded(self, run_id: str) -> AgentRun:
        run = self._runs[run_id]
        run.status = AgentRunStatus.SUCCEEDED
        run.decision = "finish"
        run.next_state = "DONE"
        return run


class SQLiteAgentRunStore:
    COMPONENT = "agent_runs"
    TARGET_VERSION = 1

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            migrate_component(
                connection,
                component=self.COMPONENT,
                target_version=self.TARGET_VERSION,
                migrations={
                    1: """
                    CREATE TABLE IF NOT EXISTS agent_runs (
                        id TEXT PRIMARY KEY,
                        goal TEXT NOT NULL,
                        project_id TEXT,
                        status TEXT NOT NULL,
                        plan_json TEXT NOT NULL,
                        decision TEXT,
                        next_state TEXT
                    );
                    """,
                },
            )

    def create(self, run: AgentRun) -> AgentRun:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO agent_runs(
                    id, goal, project_id, status, plan_json, decision, next_state
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                _run_params(run),
            )
        return run

    def get(self, run_id: str) -> AgentRun | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return _run_from_row(row)

    def list_runs(self) -> list[AgentRun]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM agent_runs ORDER BY id ASC").fetchall()
        return [_run_from_row(row) for row in rows]

    def replace(self, run: AgentRun) -> AgentRun:
        self.create(run)
        return run

    def mark_planned(self, run_id: str, plan: list[PlanItem]) -> AgentRun:
        return self._update(
            run_id,
            status=AgentRunStatus.PLANNED,
            plan=plan,
            decision="continue",
            next_state="RETRIEVE",
        )

    def mark_waiting_user(self, run_id: str, plan: list[PlanItem]) -> AgentRun:
        return self._update(
            run_id,
            status=AgentRunStatus.WAITING_USER,
            plan=plan,
            decision="ask_user",
            next_state="ASK_USER",
        )

    def mark_stopped(self, run_id: str, plan: list[PlanItem]) -> AgentRun:
        return self._update(
            run_id,
            status=AgentRunStatus.STOPPED,
            plan=plan,
            decision="stop",
            next_state="STOP",
        )

    def mark_running(self, run_id: str, *, decision: str, next_state: str) -> AgentRun:
        run = self.get(run_id)
        if run is None:
            raise KeyError(run_id)
        return self._update(
            run_id,
            status=AgentRunStatus.RUNNING,
            plan=run.plan,
            decision=decision,
            next_state=next_state,
        )

    def mark_succeeded(self, run_id: str) -> AgentRun:
        run = self.get(run_id)
        if run is None:
            raise KeyError(run_id)
        return self._update(
            run_id,
            status=AgentRunStatus.SUCCEEDED,
            plan=run.plan,
            decision="finish",
            next_state="DONE",
        )

    def _update(
        self,
        run_id: str,
        *,
        status: AgentRunStatus,
        plan: list[PlanItem],
        decision: str,
        next_state: str,
    ) -> AgentRun:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError(run_id)
            connection.execute(
                """
                UPDATE agent_runs
                SET status = ?, plan_json = ?, decision = ?, next_state = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    _plan_json(plan),
                    decision,
                    next_state,
                    run_id,
                ),
            )
        updated = self.get(run_id)
        if updated is None:
            raise KeyError(run_id)
        return updated

    def status_counts(self) -> dict[str, int]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM agent_runs
                GROUP BY status
                ORDER BY status
                """
            ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}

    def schema_versions(self) -> dict[str, int]:
        self.initialize()
        with self._connect() as connection:
            versions = list_schema_versions(connection)
        return {item.component: item.version for item in versions}

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection


def _run_params(run: AgentRun) -> tuple[str, str, str | None, str, str, str | None, str | None]:
    return (
        run.id,
        run.goal,
        run.project_id,
        run.status.value,
        _plan_json(run.plan),
        run.decision,
        run.next_state,
    )


def _plan_json(plan: list[PlanItem]) -> str:
    return json.dumps([item.model_dump() for item in plan], sort_keys=True)


def _run_from_row(row: sqlite3.Row) -> AgentRun:
    loaded = json.loads(str(row["plan_json"]))
    plan = [PlanItem.model_validate(item) for item in loaded] if isinstance(loaded, list) else []
    return AgentRun(
        id=str(row["id"]),
        goal=str(row["goal"]),
        project_id=str(row["project_id"]) if row["project_id"] is not None else None,
        status=AgentRunStatus(str(row["status"])),
        plan=plan,
        decision=str(row["decision"]) if row["decision"] is not None else None,
        next_state=str(row["next_state"]) if row["next_state"] is not None else None,
    )
