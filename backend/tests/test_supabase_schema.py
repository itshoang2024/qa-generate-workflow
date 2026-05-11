from pathlib import Path

from app.repositories.supabase_repository import (
    _can_retry_without_optional_task_columns,
    _without_optional_task_columns,
)


def test_supabase_schema_upgrades_existing_runs_table() -> None:
    schema_sql = (Path(__file__).resolve().parents[2] / "supabase" / "schema.sql").read_text(
        encoding="utf-8"
    )

    assert "alter table runs" in schema_sql
    assert "add column if not exists session_memory" in schema_sql
    assert "add column if not exists gdd_document_id" in schema_sql
    assert "add column if not exists source_version_id" in schema_sql
    assert "add column if not exists source_metadata" in schema_sql
    assert "add column if not exists delta_report" in schema_sql
    assert "add column if not exists signed_off_by" in schema_sql
    assert "create table if not exists risk_events" in schema_sql
    assert "notify pgrst, 'reload schema';" in schema_sql


def test_supabase_schema_includes_agent_b_task_columns() -> None:
    schema_sql = (Path(__file__).resolve().parents[2] / "supabase" / "schema.sql").read_text(
        encoding="utf-8"
    )

    assert "priority_justification text" in schema_sql
    assert "delta_status text" in schema_sql
    assert "add column if not exists priority_justification" in schema_sql
    assert "add column if not exists delta_status" in schema_sql


def test_supabase_task_upsert_can_retry_without_optional_agent_b_columns() -> None:
    exc = Exception(
        '{"message": "Could not find the \'delta_status\' column of \'qa_tasks\' '
        'in the schema cache", "code": "PGRST204"}'
    )
    row = {
        "task_id": "T-001",
        "title": "Verify clear path",
        "priority_justification": "Core gameplay.",
        "delta_status": None,
    }

    assert _can_retry_without_optional_task_columns("qa_tasks", exc) is True
    assert _can_retry_without_optional_task_columns("features", exc) is False
    assert _without_optional_task_columns(row) == {
        "task_id": "T-001",
        "title": "Verify clear path",
    }
