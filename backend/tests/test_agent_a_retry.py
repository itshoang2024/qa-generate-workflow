from __future__ import annotations

from typing import Any

from app.domain.models import (
    Feature,
    FeatureType,
    GDDSection,
    QATask,
    RunMode,
    TestCase as DomainTestCase,
    ReviewStatus,
)
from app.services.agent_a_retry import run_agent_a_with_retries
from app.services.agents import AgentClient, AgentOutputValidationError


def test_agent_a_retry_recovers_from_schema_failure() -> None:
    agent = SequencedAgentClient(
        [
            AgentOutputValidationError("bad json"),
            [_feature("F-001", ["S1"])],
        ]
    )

    result = run_agent_a_with_retries(
        agent_client=agent,
        run_id="run_1",
        sections=[_section("S1")],
        mode=RunMode.NEW_GAME,
        delta_report=None,
    )

    assert result.exhausted is False
    assert result.attempt_count == 2
    assert {issue.code for issue in result.issues} == set()
    assert agent.calls[1]["validation_feedback"][0]["code"] == "agent_a_schema_failure"


def test_agent_a_retry_recovers_from_traceability_failure() -> None:
    agent = SequencedAgentClient(
        [
            [_feature("F-001", ["S9"])],
            [_feature("F-001", ["S1"])],
        ]
    )

    result = run_agent_a_with_retries(
        agent_client=agent,
        run_id="run_1",
        sections=[_section("S1")],
        mode=RunMode.NEW_GAME,
        delta_report=None,
    )

    assert result.exhausted is False
    assert result.attempt_count == 2
    assert "missing_source_section" not in {issue.code for issue in result.issues}
    assert agent.calls[1]["validation_feedback"][0]["code"] == "missing_source_section"


def test_agent_a_retry_reruns_uncovered_sections_and_merges_features() -> None:
    agent = SequencedAgentClient(
        [
            [_feature("F-001", ["S1"])],
            [_feature("F-002", ["S2"])],
        ]
    )

    result = run_agent_a_with_retries(
        agent_client=agent,
        run_id="run_1",
        sections=[_section("S1"), _section("S2")],
        mode=RunMode.NEW_GAME,
        delta_report=None,
    )

    features = result.output["features"]
    coverage = result.output["coverage_report"]
    assert result.exhausted is False
    assert [feature.feature_id for feature in features] == ["F-001", "F-002"]
    assert coverage["uncovered_sections"] == []
    assert agent.calls[1]["target_section_ids"] == ["S2"]


def test_agent_a_retry_exhausts_after_max_attempts_and_blocks_feature() -> None:
    agent = SequencedAgentClient(
        [
            [_feature("F-001", ["S9"])],
            [_feature("F-001", ["S9"])],
            [_feature("F-001", ["S9"])],
        ]
    )

    result = run_agent_a_with_retries(
        agent_client=agent,
        run_id="run_1",
        sections=[_section("S1")],
        mode=RunMode.NEW_GAME,
        delta_report=None,
    )

    feature = result.output["features"][0]
    assert result.exhausted is True
    assert result.attempt_count == 3
    assert {issue.code for issue in result.issues} >= {
        "missing_source_section",
        "agent_a_retry_exhausted",
    }
    assert feature.review_status == ReviewStatus.BLOCKED


def test_agent_a_retry_exhausts_schema_failures_after_max_attempts() -> None:
    agent = SequencedAgentClient(
        [
            AgentOutputValidationError("bad json 1"),
            AgentOutputValidationError("bad json 2"),
            AgentOutputValidationError("bad json 3"),
        ]
    )

    result = run_agent_a_with_retries(
        agent_client=agent,
        run_id="run_1",
        sections=[_section("S1")],
        mode=RunMode.NEW_GAME,
        delta_report=None,
    )

    assert result.exhausted is True
    assert result.attempt_count == 3
    assert result.output["features"] == []
    assert {issue.code for issue in result.issues} == {
        "agent_a_schema_failure",
        "agent_a_retry_exhausted",
    }


class SequencedAgentClient(AgentClient):
    provider = "test"

    def __init__(self, outputs: list[object]) -> None:
        self.outputs = outputs
        self.calls: list[dict[str, Any]] = []

    def analyze_gdd(
        self,
        run_id: str,
        sections: list[GDDSection],
        *,
        mode: RunMode = RunMode.NEW_GAME,
        delta_report: dict[str, Any] | None = None,
        validation_feedback: list[dict[str, Any]] | None = None,
        target_section_ids: list[str] | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "validation_feedback": validation_feedback,
                "target_section_ids": target_section_ids,
            }
        )
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return {
            "features": output,
            "coverage_report": {},
            "ambiguities": [],
        }

    def plan_qa_tasks(self, run_id: str) -> dict[str, list[Any]]:
        return {"epics": [], "stories": [], "tasks": []}

    def generate_test_cases(self, run_id: str, tasks: list[QATask]) -> list[DomainTestCase]:
        return []


def _section(section_id: str) -> GDDSection:
    return GDDSection(
        id=f"sec_{section_id}",
        run_id="run_1",
        section_id=section_id,
        title=f"Section {section_id}",
        level=1,
        text=f"Source text for {section_id}",
        actionable=True,
    )


def _feature(feature_id: str, source_sections: list[str]) -> Feature:
    return Feature(
        id=f"feat_{feature_id}",
        run_id="run_1",
        feature_id=feature_id,
        name=f"Feature {feature_id}",
        summary="Grounded summary",
        feature_type=FeatureType.GAMEPLAY_LOGIC,
        source_sections=source_sections,
        assignee="Ngoc Anh",
        confidence=0.9,
    )
