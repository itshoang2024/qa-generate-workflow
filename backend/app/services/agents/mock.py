from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.domain.models import (
    DeltaStatus,
    Feature,
    GDDSection,
    QATask,
    ReviewStatus,
    RunMode,
    TestCase,
    TestCategory,
    TestType,
    TaskDeltaStatus,
)
from app.services.agents import AgentClient
from app.services.agents.contracts import AgentAOutput, AgentBOutput


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
        normalized_features = [
            _agent_a_feature_payload(item, mode, delta_report)
            for item in fixture["features"]
        ]
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
        feature_context_by_id = _agent_b_feature_context_by_id(
            fixture,
            hil_context,
            approved_feature_ids,
        )
        agent_output = AgentBOutput.model_validate(
            {"epics": _agent_b_epic_payloads(fixture["epics"], feature_context_by_id)}
        )
        return agent_output.to_domain_plan(
            run_id,
            feature_context_by_id=feature_context_by_id,
        )

    def plan_epics(
        self,
        run_id: str,
        *,
        hil_context: dict[str, object],
    ) -> dict[str, object]:
        plan = self.plan_qa_tasks(run_id, hil_context=hil_context)
        return {"epics": plan["epics"]}

    def plan_stories(
        self,
        run_id: str,
        *,
        epic: dict[str, object],
        features: list[dict[str, object]],
        source_text: dict[str, str],
        story_seq_offset: int,
    ) -> dict[str, object]:
        _ = source_text, story_seq_offset
        feature_ids = [
            str(feature["feature_id"])
            for feature in features
            if isinstance(feature, dict) and isinstance(feature.get("feature_id"), str)
        ]
        plan = self.plan_qa_tasks(
            run_id,
            hil_context={
                "approved_feature_ids": feature_ids,
                "approved_features": features,
            },
        )
        epic_id = str(epic.get("epic_id", ""))
        stories = [story for story in plan["stories"] if story.epic_id == epic_id]
        return {"epic_id": epic_id, "stories": stories}

    def plan_tasks(
        self,
        run_id: str,
        *,
        story: dict[str, object],
        feature: dict[str, object],
        source_text: dict[str, str],
        task_seq_offset: int,
        past_corrections: list[dict[str, object]] | None = None,
        existing_tasks: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        _ = feature, source_text, task_seq_offset, past_corrections, existing_tasks
        fixture = self._load_fixture()
        feature_context_by_id = _agent_b_feature_context_by_id(fixture, None, None)
        agent_output = AgentBOutput.model_validate(
            {"epics": _agent_b_epic_payloads(fixture["epics"], feature_context_by_id)}
        )
        plan = agent_output.to_domain_plan(
            run_id,
            feature_context_by_id=feature_context_by_id,
        )
        story_id = str(story.get("story_id", ""))
        tasks = [task for task in plan["tasks"] if task.story_id == story_id]
        return {"story_id": story_id, "tasks": tasks}

    def generate_test_cases(
        self,
        run_id: str,
        tasks: list[QATask],
        *,
        features: list[Feature] | None = None,
        sections: list[GDDSection] | None = None,
    ) -> list[TestCase]:
        _ = features, sections
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


def _agent_a_feature_payload(
    item: dict[str, object],
    mode: RunMode,
    delta_report: dict[str, object] | None,
) -> dict[str, object]:
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
    payload["delta_status"] = _feature_delta_status(item, mode, delta_report)
    return payload


def _feature_delta_status(
    item: dict[str, object],
    mode: RunMode,
    delta_report: dict[str, object] | None,
) -> str | None:
    if mode != RunMode.DELTA:
        return None
    if not delta_report:
        return DeltaStatus.UNCHANGED.value

    buckets = delta_report.get("buckets")
    if not isinstance(buckets, dict):
        return DeltaStatus.UNCHANGED.value

    source_sections = {
        section_id
        for section_id in item.get("source_sections", [])
        if isinstance(section_id, str)
    }
    if not source_sections:
        return DeltaStatus.UNCHANGED.value

    status_by_section: dict[str, str] = {}
    for status in DeltaStatus:
        raw_section_ids = buckets.get(status.value, [])
        if isinstance(raw_section_ids, list):
            for section_id in raw_section_ids:
                if isinstance(section_id, str):
                    status_by_section[section_id] = status.value

    section_statuses = {
        status_by_section.get(section_id, DeltaStatus.UNCHANGED.value)
        for section_id in source_sections
    }
    if section_statuses == {DeltaStatus.REMOVED.value}:
        return DeltaStatus.REMOVED.value
    if DeltaStatus.MODIFIED.value in section_statuses:
        return DeltaStatus.MODIFIED.value
    if DeltaStatus.NEW.value in section_statuses:
        return DeltaStatus.NEW.value
    return DeltaStatus.UNCHANGED.value


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


def _agent_b_feature_context_by_id(
    fixture: dict[str, object],
    hil_context: dict[str, object] | None,
    approved_feature_ids: set[str] | None,
) -> dict[str, dict[str, object]]:
    context_features = (hil_context or {}).get("approved_features", [])
    if isinstance(context_features, list) and context_features:
        return {
            str(feature["feature_id"]): dict(feature)
            for feature in context_features
            if isinstance(feature, dict)
            and isinstance(feature.get("feature_id"), str)
            and (
                approved_feature_ids is None
                or str(feature["feature_id"]) in approved_feature_ids
            )
        }

    feature_context_by_id: dict[str, dict[str, object]] = {}
    for feature in fixture.get("features", []):
        if not isinstance(feature, dict):
            continue
        feature_id = feature.get("feature_id")
        if not isinstance(feature_id, str):
            continue
        if approved_feature_ids is not None and feature_id not in approved_feature_ids:
            continue
        feature_context_by_id[feature_id] = {
            "feature_id": feature_id,
            "name": feature.get("name", ""),
            "summary": feature.get("summary", ""),
            "feature_type": feature.get("feature_type"),
            "source_sections": feature.get("source_sections", []),
            "key_behaviors": feature.get("key_behaviors", []),
            "dependencies": feature.get("dependencies", []),
            "confidence": feature.get("confidence", 1.0),
            "delta_status": feature.get("delta_status"),
        }
    return feature_context_by_id


def _agent_b_epic_payloads(
    fixture_epics: object,
    feature_context_by_id: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    if not isinstance(fixture_epics, list):
        return []

    epics: list[dict[str, object]] = []
    for epic_data in fixture_epics:
        if not isinstance(epic_data, dict):
            continue
        stories = [
            story
            for story in (
                _agent_b_story_payload(story_data, feature_context_by_id)
                for story_data in epic_data.get("stories", [])
                if isinstance(story_data, dict)
            )
            if story is not None
        ]
        if not stories:
            continue
        feature_ids = sorted(_story_feature_ids(stories))
        epics.append(
            {
                "epic_id": epic_data["epic_id"],
                "title": epic_data["title"],
                "description": epic_data["description"],
                "feature_ids": feature_ids,
                "external_id": epic_data["external_id"],
                "stories": stories,
            }
        )
    return epics


def _story_feature_ids(stories: list[dict[str, object]]) -> set[str]:
    feature_ids: set[str] = set()
    for story in stories:
        feature_id = story.get("feature_id")
        if isinstance(feature_id, str):
            feature_ids.add(feature_id)
        tasks = story.get("tasks", [])
        if isinstance(tasks, list):
            for task in tasks:
                if isinstance(task, dict) and isinstance(task.get("feature_id"), str):
                    feature_ids.add(str(task["feature_id"]))
    return feature_ids


def _agent_b_story_payload(
    story_data: dict[str, object],
    feature_context_by_id: dict[str, dict[str, object]],
) -> dict[str, object] | None:
    raw_tasks = story_data.get("tasks", [])
    if not isinstance(raw_tasks, list):
        return None

    tasks: list[dict[str, object]] = []
    for task_data in raw_tasks:
        if not isinstance(task_data, dict):
            continue
        task_feature_id = task_data.get("feature_id")
        if not isinstance(task_feature_id, str):
            continue
        feature_context = feature_context_by_id.get(task_feature_id)
        if feature_context is None:
            continue
        delta_status = feature_context.get("delta_status")
        if delta_status == DeltaStatus.UNCHANGED.value:
            continue
        if delta_status == DeltaStatus.REMOVED.value:
            tasks.append(_archive_task_payload(task_data, feature_context))
            continue
        tasks.append(_task_payload(task_data, feature_context))
    if not tasks:
        return None

    story_feature_id = story_data.get("feature_id")
    if not isinstance(story_feature_id, str) or story_feature_id not in feature_context_by_id:
        story_feature_id = str(tasks[0]["feature_id"])
    story_delta_status = feature_context_by_id.get(story_feature_id, {}).get("delta_status")

    return {
        "story_id": story_data["story_id"],
        "title": _story_title(story_data, story_delta_status),
        "description": story_data["description"],
        "feature_id": story_feature_id,
        "acceptance_criteria": story_data.get("acceptance_criteria", []),
        "external_id": story_data["external_id"],
        "tasks": tasks,
    }


def _task_payload(
    task_data: dict[str, object],
    feature_context: dict[str, object],
) -> dict[str, object]:
    delta_status = feature_context.get("delta_status")
    payload = dict(task_data)
    payload["priority_justification"] = _priority_justification(task_data, feature_context)
    if delta_status == DeltaStatus.MODIFIED.value:
        payload["title"] = _bounded_title(f"Update and retest {task_data['title']}")
        payload["description"] = (
            "Update the existing QA coverage for this modified GDD behavior, then retest "
            f"the original pass criteria. {task_data['description']}"
        )
        payload["delta_status"] = TaskDeltaStatus.UPDATE_RETEST.value
    elif delta_status == DeltaStatus.NEW.value:
        payload["delta_status"] = TaskDeltaStatus.NEW.value
    else:
        payload["delta_status"] = None
    return payload


def _archive_task_payload(
    task_data: dict[str, object],
    feature_context: dict[str, object],
) -> dict[str, object]:
    feature_id = str(feature_context["feature_id"])
    feature_name = str(feature_context.get("name") or feature_id)
    source_sections = feature_context.get("source_sections")
    if not isinstance(source_sections, list) or not source_sections:
        source_sections = ["removed-source"]
    return {
        "task_id": str(task_data.get("task_id") or "T-001"),
        "feature_id": feature_id,
        "title": _bounded_title(f"Archive QA coverage for removed {feature_name}"),
        "description": (
            "Confirm that this removed GDD scope should be archived from active QA "
            "coverage, then close or update any linked Notion records."
        ),
        "assignee": str(feature_context.get("assignee") or "QA Lead"),
        "priority": "P1",
        "priority_justification": (
            "Removed DELTA scope needs Lead confirmation before old QA records are archived."
        ),
        "estimate": "S",
        "source_sections": source_sections,
        "external_id": f"snake-escape-{feature_id}-ARCHIVE",
        "delta_status": TaskDeltaStatus.ARCHIVE.value,
        "confidence": 0.7,
    }


def _story_title(story_data: dict[str, object], delta_status: object) -> str:
    if delta_status == DeltaStatus.MODIFIED.value:
        return f"QA updates coverage for {story_data['title']}"
    if delta_status == DeltaStatus.REMOVED.value:
        return f"QA archives removed scope for {story_data['title']}"
    return str(story_data["title"])


def _priority_justification(
    task_data: dict[str, object],
    feature_context: dict[str, object],
) -> str:
    priority = task_data.get("priority", "P1")
    source_sections = feature_context.get("source_sections", [])
    source = ", ".join(str(section) for section in source_sections[:2]) if isinstance(source_sections, list) else ""
    if not source:
        source = str(task_data.get("source_sections", ["GDD"])[0])
    return f"{priority} priority follows the approved feature scope cited from {source}."


def _bounded_title(title: str) -> str:
    return title if len(title) <= 100 else f"{title[:97].rstrip()}..."
