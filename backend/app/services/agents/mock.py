from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.domain.models import (
    Epic,
    GDDSection,
    QATask,
    ReviewStatus,
    RunMode,
    Story,
    TestCase,
    TestCategory,
    TestType,
)
from app.services.agents import AgentClient
from app.services.agents.contracts import AgentAOutput


class MockAgentClient(AgentClient):
    provider = "mock"

    def __init__(self, fixture_path: Path) -> None:
        self.fixture_path = fixture_path

    def analyze_gdd(
        self,
        run_id: str,
        sections: list[GDDSection],
        *,
        mode: RunMode = RunMode.NEW_GAME,
        delta_report: dict[str, object] | None = None,
        validation_feedback: list[dict[str, object]] | None = None,
        target_section_ids: list[str] | None = None,
    ) -> dict[str, object]:
        fixture = self._load_fixture()
        actionable = [section.section_id for section in sections if section.actionable]
        normalized_features = [_agent_a_feature_payload(item, mode) for item in fixture["features"]]
        covered = {
            source
            for feature in normalized_features
            for source in feature["source_sections"]
            if isinstance(source, str)
        }
        uncovered = [section_id for section_id in actionable if section_id not in covered]
        agent_output = AgentAOutput.model_validate(
            {
                "features": normalized_features,
                "coverage_report": {
                    "total_input_sections": len(actionable),
                    "covered_sections": sorted(covered),
                    "uncovered_sections": uncovered,
                },
                "ambiguities": [_agent_a_ambiguity_payload(item) for item in fixture["ambiguities"]],
            }
        )
        features = agent_output.to_domain_features(
            run_id,
            feature_ambiguities={
                str(item["feature_id"]): list(item.get("ambiguities", []))
                for item in fixture["features"]
            },
        )
        return {
            "features": features,
            "coverage_report": agent_output.coverage_report.model_dump(mode="json"),
            "ambiguities": [
                ambiguity.model_dump(mode="json")
                for ambiguity in agent_output.ambiguities
            ],
        }

    def plan_qa_tasks(
        self,
        run_id: str,
        *,
        hil_context: dict[str, object] | None = None,
    ) -> dict[str, list[object]]:
        fixture = self._load_fixture()
        approved_feature_ids = _approved_feature_ids(hil_context)
        epics: list[Epic] = []
        stories: list[Story] = []
        tasks: list[QATask] = []

        for epic_data in fixture["epics"]:
            epic_feature_ids = [
                feature_id
                for feature_id in epic_data["feature_ids"]
                if approved_feature_ids is None or feature_id in approved_feature_ids
            ]
            if not epic_feature_ids:
                continue
            epics.append(
                Epic(
                    id=f"epic_{uuid4().hex[:12]}",
                    run_id=run_id,
                    review_status=ReviewStatus.AUTO_APPROVED,
                    **{
                        key: value
                        for key, value in epic_data.items()
                        if key not in {"stories", "feature_ids"}
                    },
                    feature_ids=epic_feature_ids,
                )
            )
            for story_data in epic_data["stories"]:
                if (
                    approved_feature_ids is not None
                    and story_data["feature_id"] not in approved_feature_ids
                ):
                    continue
                stories.append(
                    Story(
                        id=f"story_{uuid4().hex[:12]}",
                        run_id=run_id,
                        epic_id=epic_data["epic_id"],
                        review_status=ReviewStatus.AUTO_APPROVED,
                        **{key: value for key, value in story_data.items() if key != "tasks"},
                    )
                )
                for task_data in story_data["tasks"]:
                    if (
                        approved_feature_ids is not None
                        and task_data["feature_id"] not in approved_feature_ids
                    ):
                        continue
                    confidence = task_data["confidence"]
                    tasks.append(
                        QATask(
                            id=f"task_{uuid4().hex[:12]}",
                            run_id=run_id,
                            epic_id=epic_data["epic_id"],
                            story_id=story_data["story_id"],
                            review_status=ReviewStatus.AUTO_APPROVED
                            if confidence >= 0.85
                            else ReviewStatus.NEEDS_REVIEW,
                            **task_data,
                        )
                    )

        return {"epics": epics, "stories": stories, "tasks": tasks}

    def generate_test_cases(self, run_id: str, tasks: list[QATask]) -> list[TestCase]:
        test_cases: list[TestCase] = []
        sequence = 1
        for task in tasks:
            templates = [
                (TestCategory.POSITIVE, TestType.FUNCTIONAL, "happy path"),
                (TestCategory.NEGATIVE, TestType.REGRESSION, "blocked or invalid action"),
                (TestCategory.EDGE, TestType.FUNCTIONAL, "boundary condition"),
                (TestCategory.INTEGRATION, TestType.INTEGRATION, "linked feature flow"),
            ]
            for category, case_type, angle in templates:
                public_id = f"TC-{sequence:04d}"
                test_cases.append(
                    TestCase(
                        id=f"tc_{uuid4().hex[:12]}",
                        run_id=run_id,
                        test_case_id=public_id,
                        title=f"{task.title} - {category.value.title()}",
                        type=case_type,
                        category=category,
                        priority=task.priority,
                        preconditions=[
                            "Snake Escape demo project is loaded.",
                            f"QA task {task.task_id} is ready for test case generation.",
                        ],
                        steps=[
                            f"Open the feature area for {task.title}.",
                            f"Execute the {angle} scenario described by the QA task.",
                            "Record the observed result and compare it with the expected behavior.",
                        ],
                        expected_result=(
                            f"The {angle} scenario for {task.title} matches the GDD-backed "
                            "acceptance criteria without unsupported behavior."
                        ),
                        related_task_id=task.task_id,
                        source_sections=task.source_sections,
                        external_id=f"{task.external_id}-TC-{sequence:02d}",
                        confidence=task.confidence,
                        dedup_flag=task.dedup_flag,
                        cross_cutting_flag=task.cross_cutting_flag,
                        test_data={"source_task_external_id": task.external_id, "category": category.value},
                        review_status=ReviewStatus.AUTO_APPROVED
                        if task.review_status == ReviewStatus.AUTO_APPROVED
                        else ReviewStatus.NEEDS_REVIEW,
                    )
                )
                sequence += 1
        return test_cases

    def _load_fixture(self) -> dict[str, object]:
        return json.loads(self.fixture_path.read_text(encoding="utf-8"))


def _agent_a_feature_payload(item: dict[str, object], mode: RunMode) -> dict[str, object]:
    payload = {
        key: item[key]
        for key in (
            "feature_id",
            "name",
            "summary",
            "feature_type",
            "source_sections",
            "key_behaviors",
            "dependencies",
            "confidence",
        )
    }
    payload["delta_status"] = "UNCHANGED" if mode == RunMode.DELTA else None
    return payload


def _agent_a_ambiguity_payload(item: dict[str, object]) -> dict[str, object]:
    return {
        "section_id": item["section_id"],
        "issue": item.get("issue") or item.get("reason") or "Ambiguous GDD section.",
        "suggested_action": item.get("suggested_action") or "ask_user",
    }


def _approved_feature_ids(hil_context: dict[str, object] | None) -> set[str] | None:
    if hil_context is None:
        return None
    raw_ids = hil_context.get("approved_feature_ids")
    if not isinstance(raw_ids, list):
        return None
    return {feature_id for feature_id in raw_ids if isinstance(feature_id, str)}
