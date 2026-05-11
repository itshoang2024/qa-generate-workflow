from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.domain.models import GDDSection, RunMode
from app.services.agents import AgentClient
from app.services.agents.contracts import (
    AGENT_A_FEATURE_ID_PATTERN,
    AGENT_A_NAME_MAX_LENGTH,
    AGENT_A_RESPONSE_SCHEMA,
    AGENT_A_SUMMARY_MAX_LENGTH,
    AgentAOutput,
)
from app.services.agents.factory import build_agent_client
from app.services.agents.mock import MockAgentClient
from app.services.agents.openai import OpenAIAgentClient
from app.services.notion import NotionSyncClient
from app.services.notion.mock import MockNotionSyncClient


def test_mock_agent_client_implements_agent_client_contract() -> None:
    fixture_path = Path(__file__).resolve().parents[2] / "data" / "snake_escape_fixture.json"

    client = MockAgentClient(fixture_path)

    assert isinstance(client, AgentClient)


def test_mock_agent_a_validates_structured_contract() -> None:
    fixture_path = Path(__file__).resolve().parents[2] / "data" / "snake_escape_fixture.json"
    client = MockAgentClient(fixture_path)

    output = client.analyze_gdd("run_1", _agent_a_sections())

    assert len(output["features"]) == 8
    assert output["coverage_report"]["total_input_sections"] == 3
    assert output["features"][0].source_sections
    assert output["features"][0].confidence == 0.93
    assert output["features"][0].delta_status is None
    assert {"section_id", "issue", "suggested_action"} <= set(output["ambiguities"][0])


def test_mock_agent_a_sets_delta_status_in_delta_mode() -> None:
    fixture_path = Path(__file__).resolve().parents[2] / "data" / "snake_escape_fixture.json"
    client = MockAgentClient(fixture_path)

    output = client.analyze_gdd("run_1", _agent_a_sections(), mode=RunMode.DELTA)

    assert {feature.delta_status.value for feature in output["features"]} == {"UNCHANGED"}


def test_agent_a_contract_rejects_missing_source_sections() -> None:
    payload = {
        "features": [
            {
                "feature_id": "F-999",
                "name": "Unsupported Feature",
                "summary": "No cited source section.",
                "feature_type": "gameplay_logic",
                "source_sections": [],
                "key_behaviors": [],
                "dependencies": [],
                "confidence": 0.9,
                "delta_status": None,
            }
        ],
        "coverage_report": {
            "total_input_sections": 1,
            "covered_sections": [],
            "uncovered_sections": ["S1"],
        },
        "ambiguities": [],
    }

    with pytest.raises(ValidationError):
        AgentAOutput.model_validate(payload)


def test_agent_a_contract_rejects_non_canonical_feature_id() -> None:
    payload = {
        "features": [
            {
                "feature_id": "F01",
                "name": "Unsupported Feature ID",
                "summary": "Feature ID must use the canonical zero-padded format.",
                "feature_type": "gameplay_logic",
                "source_sections": ["S1"],
                "key_behaviors": [],
                "dependencies": [],
                "confidence": 0.9,
                "delta_status": None,
            }
        ],
        "coverage_report": {
            "total_input_sections": 1,
            "covered_sections": ["S1"],
            "uncovered_sections": [],
        },
        "ambiguities": [],
    }

    with pytest.raises(ValidationError):
        AgentAOutput.model_validate(payload)


def test_agent_a_response_schema_matches_pydantic_limits() -> None:
    feature_schema = AGENT_A_RESPONSE_SCHEMA["properties"]["features"]["items"]
    properties = feature_schema["properties"]

    assert properties["feature_id"]["pattern"] == AGENT_A_FEATURE_ID_PATTERN
    assert properties["name"]["maxLength"] == AGENT_A_NAME_MAX_LENGTH
    assert properties["summary"]["maxLength"] == AGENT_A_SUMMARY_MAX_LENGTH
    assert properties["source_sections"]["minItems"] == 1
    assert properties["confidence"]["minimum"] == 0
    assert properties["confidence"]["maximum"] == 1


def test_build_agent_client_rejects_unsupported_provider(tmp_path: Path) -> None:
    settings = replace(get_settings(env_file=tmp_path / ".env"), ai_provider="bogus")

    with pytest.raises(ValueError, match="Unsupported AI_PROVIDER"):
        build_agent_client(settings)


def test_build_agent_client_requires_openai_key(tmp_path: Path) -> None:
    settings = replace(
        get_settings(env_file=tmp_path / ".env"),
        ai_provider="openai",
        openai_api_key=None,
    )

    with pytest.raises(ValueError, match="requires OPENAI_API_KEY"):
        build_agent_client(settings)


def test_build_agent_client_returns_openai_agent_a_with_mock_fallback(tmp_path: Path) -> None:
    settings = replace(
        get_settings(env_file=tmp_path / ".env"),
        ai_provider="openai",
        openai_api_key="sk-test",
    )

    client = build_agent_client(settings)

    assert isinstance(client, OpenAIAgentClient)
    assert client.provider_for("analyze_gdd") == "openai"
    assert client.provider_for("plan_qa_tasks") == "mock"


def test_mock_agent_b_consumes_hil1_approved_feature_ids() -> None:
    fixture_path = Path(__file__).resolve().parents[2] / "data" / "snake_escape_fixture.json"
    client = MockAgentClient(fixture_path)

    output = client.plan_qa_tasks(
        "run_1",
        hil_context={"approved_feature_ids": ["F-001"]},
    )

    assert len(output["epics"]) == 1
    assert output["epics"][0].feature_ids == ["F-001"]
    assert {story.feature_id for story in output["stories"]} == {"F-001"}
    assert {task.feature_id for task in output["tasks"]} == {"F-001"}
    assert len(output["tasks"]) == 2


def test_mock_notion_sync_client_implements_notion_contract() -> None:
    client = MockNotionSyncClient()

    assert isinstance(client, NotionSyncClient)


def _agent_a_sections() -> list[GDDSection]:
    return [
        GDDSection(
            id=f"section_{index}",
            run_id="run_1",
            section_id=section_id,
            title=f"Section {index}",
            level=1,
            text="Actionable gameplay and UI text.",
            actionable=True,
        )
        for index, section_id in enumerate(
            ["\u00c2\u00a72.3", "\u00c2\u00a72.4", "\u00c2\u00a72.5"],
            start=1,
        )
    ]
