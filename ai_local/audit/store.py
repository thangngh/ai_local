from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sqlite3

from ai_local.db.schema import list_schema_versions, migrate_component


@dataclass(frozen=True)
class AuditEvent:
    action: str
    target: str
    result: str
    created_at: str


def make_audit_event(action: str, target: str, result: str) -> AuditEvent:
    return AuditEvent(
        action=action,
        target=target,
        result=result,
        created_at=datetime.now(UTC).isoformat(),
    )


class InMemoryAuditStore:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self._events.append(event)

    def list_events(self) -> list[AuditEvent]:
        return list(self._events)


class SQLiteAuditStore:
    COMPONENT = "audit"
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
                    CREATE TABLE IF NOT EXISTS audit_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        action TEXT NOT NULL,
                        target TEXT NOT NULL,
                        result TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    """,
                },
            )

    def append(self, event: AuditEvent) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_events(action, target, result, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (event.action, event.target, event.result, event.created_at),
            )

    def list_events(self) -> list[AuditEvent]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT action, target, result, created_at
                FROM audit_events
                ORDER BY id
                """
            ).fetchall()
        return [
            AuditEvent(
                action=str(row["action"]),
                target=str(row["target"]),
                result=str(row["result"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def count(self) -> int:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM audit_events").fetchone()
        return int(row["count"])

    def schema_versions(self) -> dict[str, int]:
        self.initialize()
        with self._connect() as connection:
            versions = list_schema_versions(connection)
        return {item.component: item.version for item in versions}

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection
