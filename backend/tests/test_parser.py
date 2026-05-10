from pathlib import Path

import pytest

from app.services.gdd_parser import parse_docx_gdd


def test_parser_extracts_snake_headings_tables_and_notes() -> None:
    gdd_path = Path(__file__).resolve().parents[3] / "GDD Sample_Snake Escape.docx"
    if not gdd_path.exists():
        pytest.skip("Root-level Snake Escape GDD is not available.")

    parsed = parse_docx_gdd(gdd_path, run_id="run_test")

    section_ids = {section.section_id for section in parsed.sections}
    assert "§2.3" in section_ids
    assert "§12.8" in section_ids
    assert any(section.tables for section in parsed.sections)
    assert any(section.flags for section in parsed.sections)

    technical = next(section for section in parsed.sections if section.section_id == "§13")
    assert technical.actionable is False
    assert technical.actionability_reason == "external_dependency"

