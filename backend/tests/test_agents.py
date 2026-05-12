import json
from dataclasses import replace
from pathlib import Path

import pytest
import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.domain.models import GDDSection, ReviewStatus, RunMode, TaskDeltaStatus
from app.services.agents import AgentClient
from app.services.agents.contracts import (
    AGENT_A_FEATURE_ID_PATTERN,
    AGENT_A_NAME_MAX_LENGTH,
    AGENT_A_RESPONSE_SCHEMA,
    AGENT_A_SUMMARY_MAX_LENGTH,
    AGENT_B1_RESPONSE_SCHEMA,
    AGENT_B2_RESPONSE_SCHEMA,
    AGENT_B3_RESPONSE_SCHEMA,
    AGENT_B_RESPONSE_SCHEMA,
    AgentBOutput,
    AgentAOutput,
    build_agent_b1_input,
    build_agent_b2_input,
    build_agent_b3_input,
    build_agent_b_input,
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


def test_mock_agent_a_maps_delta_report_buckets_to_feature_statuses() -> None:
    fixture_path = Path(__file__).resolve().parents[2] / "data" / "snake_escape_fixture.json"
    client = MockAgentClient(fixture_path)

    output = client.analyze_gdd(
        "run_1",
        _agent_a_sections(),
        mode=RunMode.DELTA,
        delta_report={
            "buckets": {
                "NEW": ["\u00a72.3"],
                "MODIFIED": ["\u00a73.1"],
                "UNCHANGED": [],
                "REMOVED": [
                    "\u00a712.1",
                    "\u00a712.2",
                    "\u00a712.4",
                    "\u00a712.5",
                    "\u00a712.6",
                    "\u00a712.7",
                    "\u00a712.8",
                ],
            }
        },
    )

    status_by_feature = {
        feature.feature_id: feature.delta_status.value for feature in output["features"]
    }
    assert status_by_feature["F-001"] == "NEW"
    assert status_by_feature["F-002"] == "MODIFIED"
    assert status_by_feature["F-008"] == "REMOVED"


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


def test_agent_b_response_schema_requires_task_contract_fields() -> None:
    task_schema = (
        AGENT_B_RESPONSE_SCHEMA["properties"]["epics"]["items"]["properties"]["stories"]["items"][
            "properties"
        ]["tasks"]["items"]
    )
    properties = task_schema["properties"]

    assert properties["task_id"]["pattern"] == "^T-[0-9]{3,}$"
    assert properties["title"]["maxLength"] == 100
    assert properties["source_sections"]["minItems"] == 1
    assert "feature_id" in task_schema["required"]
    assert "priority_justification" in task_schema["required"]
    assert "delta_status" in task_schema["required"]


def test_agent_b_contract_normalizes_assignee_from_feature_mapping() -> None:
    agent_output = AgentBOutput.model_validate(_agent_b_payload(assignee="Minh"))

    plan = agent_output.to_domain_plan(
        "run_1",
        feature_context_by_id={
            "F-001": {
                "feature_id": "F-001",
                "feature_type": "gameplay_logic",
                "source_sections": ["\u00a72.3"],
            }
        },
    )

    task = plan["tasks"][0]
    assert task.assignee == "Ngoc Anh"
    assert task.priority_justification == "Core gameplay loop."
    assert task.delta_status is None


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
    assert client.provider_for("plan_qa_tasks") == "openai"
    assert client.provider_for("generate_test_cases") == "mock"


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


def test_mock_agent_b_applies_delta_task_behavior() -> None:
    fixture_path = Path(__file__).resolve().parents[2] / "data" / "snake_escape_fixture.json"
    client = MockAgentClient(fixture_path)

    output = client.plan_qa_tasks(
        "run_1",
        hil_context={
            "approved_feature_ids": ["F-001", "F-002", "F-003", "F-008"],
            "approved_features": [
                _approved_feature("F-001", "gameplay_logic", "UNCHANGED"),
                _approved_feature("F-002", "level_puzzle", "MODIFIED"),
                _approved_feature("F-003", "economy", "NEW"),
                _approved_feature("F-008", "backend_liveops", "REMOVED"),
            ],
        },
    )

    tasks = output["tasks"]
    assert "F-001" not in {task.feature_id for task in tasks}
    assert {
        task.delta_status for task in tasks if task.feature_id == "F-002"
    } == {TaskDeltaStatus.UPDATE_RETEST}
    assert {
        task.delta_status for task in tasks if task.feature_id == "F-003"
    } == {TaskDeltaStatus.NEW}
    archive_task = next(task for task in tasks if task.feature_id == "F-008")
    assert archive_task.delta_status == TaskDeltaStatus.ARCHIVE
    assert archive_task.review_status == ReviewStatus.NEEDS_REVIEW
    assert archive_task.assignee == "Quan"


def test_mock_agent_b_hierarchical_methods_match_bundled_fixture() -> None:
    fixture_path = Path(__file__).resolve().parents[2] / "data" / "snake_escape_fixture.json"
    client = MockAgentClient(fixture_path)
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    approved_features = [
        _approved_feature(feature["feature_id"], feature["feature_type"], None)
        for feature in fixture["features"]
    ]
    hil_context = {
        "project_id": "snake-escape",
        "approved_feature_ids": [feature["feature_id"] for feature in approved_features],
        "approved_features": approved_features,
    }

    bundled = client.plan_qa_tasks("run_1", hil_context=hil_context)
    epics = client.plan_epics("run_1", hil_context=hil_context)["epics"]
    stories = []
    tasks = []
    feature_by_id = {feature["feature_id"]: feature for feature in approved_features}
    for index, epic in enumerate(epics, start=1):
        epic_features = [feature_by_id[feature_id] for feature_id in epic.feature_ids]
        story_output = client.plan_stories(
            "run_1",
            epic=epic.model_dump(mode="json"),
            features=epic_features,
            source_text={},
            story_seq_offset=index,
        )
        stories.extend(story_output["stories"])
    for index, story in enumerate(stories, start=1):
        task_output = client.plan_tasks(
            "run_1",
            story=story.model_dump(mode="json"),
            feature=feature_by_id[story.feature_id],
            source_text={},
            task_seq_offset=index,
        )
        tasks.extend(task_output["tasks"])

    assert [epic.epic_id for epic in epics] == [epic.epic_id for epic in bundled["epics"]]
    assert [story.story_id for story in stories] == [
        story.story_id for story in bundled["stories"]
    ]
    assert [task.task_id for task in tasks] == [task.task_id for task in bundled["tasks"]]


def test_agent_b_substage_builders_trim_payloads() -> None:
    hil_context = {
        "project_id": "snake-escape",
        "mode": "NEW_GAME",
        "approved_features": [
            {
                **_approved_feature("F-001", "gameplay_logic", None),
                "summary": "x" * 300,
                "dependencies": [],
                "key_behaviors": [],
            }
        ],
        "epic_structure": {
            "epics": [{"epic_id": "HIL1-GAMEPLAY", "title": "Gameplay", "feature_ids": ["F-001"]}]
        },
    }
    b1 = build_agent_b1_input(hil_context)
    b2 = build_agent_b2_input(
        epic={"epic_id": "E-CORE", "title": "Core", "feature_ids": ["F-001"]},
        features=b1["approved_features"],
        source_text={"S1": "a" * 1400},
        story_seq_offset=1,
        project_id="snake-escape",
        mode="NEW_GAME",
    )
    b3 = build_agent_b3_input(
        story={"story_id": "S-001", "feature_id": "F-001", "acceptance_criteria": []},
        feature=b1["approved_features"][0],
        source_text={"S1": "a" * 1400},
        task_seq_offset=1,
        project_id="snake-escape",
        mode="NEW_GAME",
    )

    assert len(b1["approved_features"][0]["summary"]) == 200
    assert "dependencies" not in b1["approved_features"][0]
    assert len(b2["source_sections_text"]["S1"]) == 1200
    assert "past_corrections" not in b3
    assert AGENT_B1_RESPONSE_SCHEMA["properties"]["epics"]["items"]["properties"]["epic_id"]
    assert AGENT_B2_RESPONSE_SCHEMA["required"] == ["epic_id", "stories"]
    assert AGENT_B3_RESPONSE_SCHEMA["required"] == ["story_id", "tasks"]


def test_openai_agent_b_uses_structured_contract_and_normalized_assignee() -> None:
    fixture_path = Path(__file__).resolve().parents[2] / "data" / "snake_escape_fixture.json"
    http_client = _FakeOpenAIHTTPClient(_agent_b_payload(assignee="Minh"))
    client = OpenAIAgentClient(
        api_key="sk-test",
        model="gpt-test",
        fallback=MockAgentClient(fixture_path),
        http_client=http_client,
    )

    output = client.plan_qa_tasks(
        "run_1",
        hil_context={
            "project_id": "snake-escape",
            "approved_features": [_approved_feature("F-001", "gameplay_logic", None)],
            "epic_structure": {
                "epics": [
                    {
                        "epic_id": "E-CORE",
                        "title": "Core",
                        "feature_ids": ["F-001"],
                    }
                ]
            },
        },
    )

    request_payload = http_client.requests[0]
    assert request_payload["text"]["format"]["name"] == "agent_b_output"
    assert request_payload["text"]["format"]["schema"] == AGENT_B_RESPONSE_SCHEMA
    assert output["tasks"][0].assignee == "Ngoc Anh"
    assert output["tasks"][0].priority_justification == "Core gameplay loop."


def test_openai_agent_b1_streaming_uses_final_output_text_once() -> None:
    fixture_path = Path(__file__).resolve().parents[2] / "data" / "snake_escape_fixture.json"
    http_client = _StreamingOpenAIHTTPClient(_agent_b1_payload())
    client = OpenAIAgentClient(
        api_key="sk-test",
        model="gpt-test",
        fallback=MockAgentClient(fixture_path),
        http_client=http_client,
        stream_agent_b_substages=True,
    )

    output = client.plan_epics(
        "run_1",
        hil_context={
            "project_id": "snake-escape",
            "approved_features": [_approved_feature("F-001", "gameplay_logic", None)],
        },
    )

    assert [epic.epic_id for epic in output["epics"]] == ["E-CORE"]
    assert http_client.requests[0]["stream"] is True


def test_build_agent_b_input_includes_validation_feedback_for_retry() -> None:
    payload = build_agent_b_input(
        {
            "project_id": "snake-escape",
            "approved_feature_ids": ["F-001", "F-002"],
            "approved_features": [_approved_feature("F-001", "gameplay_logic", None)],
            "epic_structure": {
                "epics": [
                    {
                        "epic_id": "HIL1-GAMEPLAY-LOGIC",
                        "title": "Gameplay Logic Scope",
                        "feature_ids": ["F-001"],
                    }
                ]
            },
            "validation_feedback": [
                {
                    "code": "missing_agent_b_feature_coverage",
                    "target_type": "feature",
                    "target_id": "F-002",
                    "message": "Agent B omitted F-002.",
                }
            ],
        }
    )

    assert payload["validation_feedback"][0]["target_id"] == "F-002"
    assert payload["epic_grouping"][0]["epic_id"] == "HIL1-GAMEPLAY-LOGIC"


def test_openai_agent_b_falls_back_to_mock_after_transient_502() -> None:
    fixture_path = Path(__file__).resolve().parents[2] / "data" / "snake_escape_fixture.json"
    fallback = MockAgentClient(fixture_path)
    client = OpenAIAgentClient(
        api_key="sk-test",
        model="gpt-test",
        fallback=fallback,
        http_client=_FailingOpenAIHTTPClient(502),
        retry_count=0,
        retry_sleep_seconds=0,
    )

    output = client.plan_qa_tasks(
        "run_1",
        hil_context={"approved_feature_ids": ["F-001"]},
    )

    assert len(output["tasks"]) == 2
    assert client.provider_for("plan_qa_tasks") == "mock_after_openai_transient_error"


def test_openai_agent_a_falls_back_to_mock_after_read_timeout() -> None:
    fixture_path = Path(__file__).resolve().parents[2] / "data" / "snake_escape_fixture.json"
    client = OpenAIAgentClient(
        api_key="sk-test",
        model="gpt-test",
        fallback=MockAgentClient(fixture_path),
        http_client=_TimeoutOpenAIHTTPClient(),
        retry_count=0,
        retry_sleep_seconds=0,
    )

    output = client.analyze_gdd("run_1", _agent_a_sections())

    assert len(output["features"]) == 8
    assert client.provider_for("analyze_gdd") == "mock_after_openai_network_error"


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


def _agent_b_payload(assignee: str) -> dict[str, object]:
    return {
        "epics": [
            {
                "epic_id": "E-CORE",
                "title": "Core Gameplay",
                "description": "Core gameplay QA.",
                "feature_ids": ["F-001"],
                "external_id": "snake-escape-E-CORE",
                "stories": [
                    {
                        "story_id": "S-001",
                        "title": "Player can clear a path",
                        "description": "QA verifies tap-to-move behavior.",
                        "feature_id": "F-001",
                        "acceptance_criteria": ["Clear path removes the snake."],
                        "external_id": "snake-escape-E-CORE-S-001",
                        "tasks": [
                            {
                                "task_id": "T-001",
                                "feature_id": "F-001",
                                "title": "Verify clear-path snake exits",
                                "description": "Validate the clear-path behavior.",
                                "assignee": assignee,
                                "priority": "P0",
                                "priority_justification": "Core gameplay loop.",
                                "estimate": "S",
                                "source_sections": ["\u00a72.3"],
                                "external_id": "snake-escape-F-001-T-01",
                                "delta_status": None,
                                "confidence": 0.91,
                            }
                        ],
                    }
                ],
            }
        ]
    }


def _agent_b1_payload() -> dict[str, object]:
    return {
        "epics": [
            {
                "epic_id": "E-CORE",
                "title": "Core Gameplay",
                "description": "Core gameplay QA.",
                "feature_ids": ["F-001"],
                "rationale": "Groups the approved core loop feature.",
                "external_id": "snake-escape-E-CORE",
                "delta_status": None,
            }
        ]
    }


def _approved_feature(
    feature_id: str,
    feature_type: str,
    delta_status: str | None,
) -> dict[str, object]:
    return {
        "feature_id": feature_id,
        "name": f"{feature_id} Feature",
        "summary": "Approved feature summary.",
        "feature_type": feature_type,
        "source_sections": ["\u00a72.3"],
        "confidence": 0.9,
        "assignee": "Wrong",
        "review_status": "APPROVED",
        "delta_status": delta_status,
    }


class _FakeOpenAIResponse:
    text = "{}"
    status_code = 200

    def __init__(self, structured_payload: dict[str, object]) -> None:
        self.structured_payload = structured_payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return {"output_text": json.dumps(self.structured_payload)}


class _FakeOpenAIHTTPClient:
    def __init__(self, structured_payload: dict[str, object]) -> None:
        self.structured_payload = structured_payload
        self.requests: list[dict[str, object]] = []

    def post(self, *args: object, **kwargs: object) -> _FakeOpenAIResponse:
        self.requests.append(kwargs["json"])
        return _FakeOpenAIResponse(self.structured_payload)


class _StreamingOpenAIResponse:
    text = "{}"
    status_code = 200

    def __init__(self, structured_payload: dict[str, object]) -> None:
        output_text = json.dumps(structured_payload)
        split_at = len(output_text) // 2
        self.events = [
            {
                "type": "response.output_text.delta",
                "delta": output_text[:split_at],
            },
            {
                "type": "response.output_text.delta",
                "delta": output_text[split_at:],
            },
            {
                "type": "response.output_text.done",
                "text": output_text,
            },
            {
                "type": "response.completed",
                "response": {"output": []},
            },
        ]

    def __enter__(self) -> "_StreamingOpenAIResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self) -> list[str]:
        return [f"data: {json.dumps(event)}" for event in self.events] + ["data: [DONE]"]


class _StreamingOpenAIHTTPClient:
    def __init__(self, structured_payload: dict[str, object]) -> None:
        self.structured_payload = structured_payload
        self.requests: list[dict[str, object]] = []

    def stream(self, *args: object, **kwargs: object) -> _StreamingOpenAIResponse:
        self.requests.append(kwargs["json"])
        return _StreamingOpenAIResponse(self.structured_payload)


class _FailingOpenAIResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.text = "<html>Bad gateway</html>"

    def raise_for_status(self) -> None:
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        response = httpx.Response(
            self.status_code,
            request=request,
            text=self.text,
        )
        raise httpx.HTTPStatusError("OpenAI error", request=request, response=response)


class _FailingOpenAIHTTPClient:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def post(self, *args: object, **kwargs: object) -> _FailingOpenAIResponse:
        return _FailingOpenAIResponse(self.status_code)


class _TimeoutOpenAIHTTPClient:
    def post(self, *args: object, **kwargs: object) -> None:
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        raise httpx.ReadTimeout("The read operation timed out", request=request)
