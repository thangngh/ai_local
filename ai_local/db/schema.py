from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaVersion:
    component: str
    version: int


def ensure_schema_version_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_versions (
            component TEXT PRIMARY KEY,
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def schema_version(connection: sqlite3.Connection, component: str) -> int:
    ensure_schema_version_table(connection)
    row = connection.execute(
        "SELECT version FROM schema_versions WHERE component = ?",
        (component,),
    ).fetchone()
    if row is None:
        return 0
    return int(row["version"])


def set_schema_version(connection: sqlite3.Connection, component: str, version: int) -> None:
    ensure_schema_version_table(connection)
    connection.execute(
        """
        INSERT INTO schema_versions(component, version, applied_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(component) DO UPDATE SET
            version = excluded.version,
            applied_at = excluded.applied_at
        """,
        (component, version),
    )


def list_schema_versions(connection: sqlite3.Connection) -> list[SchemaVersion]:
    ensure_schema_version_table(connection)
    rows = connection.execute(
        "SELECT component, version FROM schema_versions ORDER BY component"
    ).fetchall()
    return [
        SchemaVersion(component=str(row["component"]), version=int(row["version"]))
        for row in rows
    ]


def migrate_component(
    connection: sqlite3.Connection,
    *,
    component: str,
    target_version: int,
    migrations: dict[int, str],
) -> None:
    current = schema_version(connection, component)
    if current > target_version:
        msg = f"{component} schema version {current} is newer than supported {target_version}"
        raise ValueError(msg)
    for version in range(current + 1, target_version + 1):
        statement = migrations.get(version)
        if statement is None:
            msg = f"{component} migration {version} is missing"
            raise ValueError(msg)
        connection.executescript(statement)
        set_schema_version(connection, component, version)
