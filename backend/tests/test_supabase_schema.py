from pathlib import Path


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
