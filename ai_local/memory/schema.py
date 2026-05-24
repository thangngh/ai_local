MEMORY_SCHEMA_COLUMNS: dict[str, tuple[str, ...]] = {
    "memory_items": (
        "id",
        "claim",
        "memory_level",
        "scope",
        "source",
        "source_hash",
        "confidence",
        "risk",
        "status",
        "role",
        "sensitivity",
        "confirmed_by",
        "created_at",
        "updated_at",
        "expires_at",
    ),
    "memory_evidence": (
        "id",
        "memory_id",
        "evidence_type",
        "ref",
        "summary",
        "weight",
        "created_at",
    ),
    "memory_conflicts": (
        "id",
        "memory_id",
        "conflicting_memory_id",
        "conflict_score",
        "reason",
        "status",
        "created_at",
    ),
    "memory_updates": (
        "id",
        "memory_id",
        "update_type",
        "old_status",
        "new_status",
        "reason",
        "created_at",
    ),
    "memory_usage": (
        "id",
        "memory_id",
        "run_id",
        "retrieval_score",
        "used_as",
        "outcome",
        "created_at",
    ),
}


def schema_has_tables(required_tables: list[str]) -> bool:
    return all(table in MEMORY_SCHEMA_COLUMNS for table in required_tables)


def schema_has_columns(table: str, required_columns: list[str]) -> bool:
    columns = MEMORY_SCHEMA_COLUMNS.get(table, ())
    return all(column in columns for column in required_columns)
