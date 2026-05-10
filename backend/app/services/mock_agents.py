from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.domain.models import (
    Epic,
    Feature,
    FeatureType,
    GDDSection,
    QATask,
    ReviewStatus,
    Story,
    TestCase,
    TestCategory,
    TestType,
)
from app.domain.qa_roster import QA_ASSIGNEE_BY_FEATURE_TYPE


class MockAgentClient:
    def __init__(self, fixture_path: Path) -> None:
        self.fixture_path = fixture_path

    def analyze_gdd(self, run_id: str, sections: list[GDDSection]) -> dict[str, object]:
        fixture = self._load_fixture()
        features = [
            Feature(
                id=f"feat_{uuid4().hex[:12]}",
                run_id=run_id,
                review_status=ReviewStatus.AUTO_APPROVED
                if item["confidence"] >= 0.85
                else ReviewStatus.NEEDS_REVIEW,
                assignee=QA_ASSIGNEE_BY_FEATURE_TYPE[FeatureType(item["feature_type"])],
                **item,
            )
            for item in fixture["features"]
        ]
        covered = {source for feature in features for source in feature.source_sections}
        actionable = [section.section_id for section in sections if section.actionable]
        uncovered = [section_id for section_id in actionable if section_id not in covered]
        return {
            "features": features,
            "coverage_report": {
                "actionable_sections": actionable,
                "covered_sections": sorted(covered),
                "uncovered_sections": uncovered,
            },
            "ambiguities": fixture["ambiguities"],
        }

    def plan_qa_tasks(self, run_id: str) -> dict[str, list[object]]:
        fixture = self._load_fixture()
        epics: list[Epic] = []
        stories: list[Story] = []
        tasks: list[QATask] = []

        for epic_data in fixture["epics"]:
            epics.append(
                Epic(
                    id=f"epic_{uuid4().hex[:12]}",
                    run_id=run_id,
                    review_status=ReviewStatus.AUTO_APPROVED,
                    **{key: value for key, value in epic_data.items() if key != "stories"},
                )
            )
            for story_data in epic_data["stories"]:
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
