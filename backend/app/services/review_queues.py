from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.domain.models import (
    Feature,
    QATask,
    ReviewQueue,
    ReviewQueueGroup,
    ReviewQueueItem,
    ReviewStatus,
    TestCase,
)
from app.repositories.workflow_repository import WorkflowRepository

QUEUE_STATUSES = {ReviewStatus.NEEDS_REVIEW, ReviewStatus.BLOCKED}
QA_LEAD_REVIEWER = "QA Lead"


def build_review_queue(
    repository: WorkflowRepository,
    run_id: str,
    hil_tier: str,
) -> ReviewQueue:
    normalized_tier = _normalize_hil_tier(hil_tier)
    if normalized_tier == "HIL-0":
        items = _hil0_items(repository, run_id)
    elif normalized_tier == "HIL-1":
        items = _hil1_items(repository, run_id)
    elif normalized_tier == "HIL-2":
        items = _hil2_items(repository, run_id)
    else:
        items = _hil3_items(repository, run_id)

    groups = _group_queue_items(items)
    return ReviewQueue(
        run_id=run_id,
        hil_tier=normalized_tier,
        group_by=["reviewer", "feature_id", "epic_id"],
        item_count=len(items),
        groups=groups,
    )


def _normalize_hil_tier(value: str) -> str:
    normalized = value.strip().upper().replace("_", "-")
    if normalized in {"0", "HIL0"}:
        return "HIL-0"
    if normalized in {"1", "HIL1"}:
        return "HIL-1"
    if normalized in {"2", "HIL2"}:
        return "HIL-2"
    if normalized in {"3", "HIL3"}:
        return "HIL-3"
    if normalized in {"HIL-0", "HIL-1", "HIL-2", "HIL-3"}:
        return normalized
    raise ValueError("hil_tier must be one of HIL-0, HIL-1, HIL-2, or HIL-3.")


def _hil0_items(repository: WorkflowRepository, run_id: str) -> list[ReviewQueueItem]:
    return [
        ReviewQueueItem(
            target_type="hil0_question",
            target_id=question.id,
            title=question.title,
            reviewer=QA_LEAD_REVIEWER,
            lane="BATCH",
            review_status=question.status,
            payload=question.model_dump(mode="json"),
        )
        for question in repository.list_hil0_questions(run_id)
        if question.status == "OPEN"
    ]


def _hil1_items(repository: WorkflowRepository, run_id: str) -> list[ReviewQueueItem]:
    epics = repository.list_epics(run_id)
    epic_by_feature = {
        feature_id: epic.epic_id
        for epic in epics
        for feature_id in epic.feature_ids
    }
    items: list[ReviewQueueItem] = []
    for feature in repository.list_features(run_id):
        if feature.review_status in QUEUE_STATUSES:
            items.append(_feature_item(feature, epic_by_feature.get(feature.feature_id)))
    for epic in epics:
        if epic.review_status in QUEUE_STATUSES:
            items.append(
                ReviewQueueItem(
                    target_type="epic",
                    target_id=epic.epic_id,
                    title=epic.title,
                    reviewer=QA_LEAD_REVIEWER,
                    lane="BATCH",
                    review_status=epic.review_status.value,
                    epic_id=epic.epic_id,
                    payload=epic.model_dump(mode="json"),
                )
            )
    return items


def _hil2_items(repository: WorkflowRepository, run_id: str) -> list[ReviewQueueItem]:
    return [
        _task_item(task)
        for task in repository.list_tasks(run_id)
        if task.review_status in QUEUE_STATUSES
    ]


def _hil3_items(repository: WorkflowRepository, run_id: str) -> list[ReviewQueueItem]:
    tasks_by_id = {task.task_id: task for task in repository.list_tasks(run_id)}
    items: list[ReviewQueueItem] = []
    for test_case in repository.list_test_cases(run_id):
        if test_case.review_status not in QUEUE_STATUSES:
            continue
        task = tasks_by_id.get(test_case.related_task_id)
        items.append(_test_case_item(test_case, task))
    return items


def _feature_item(feature: Feature, epic_id: str | None) -> ReviewQueueItem:
    return ReviewQueueItem(
        target_type="feature",
        target_id=feature.feature_id,
        title=feature.name,
        reviewer=QA_LEAD_REVIEWER,
        lane=feature.lane,
        review_status=feature.review_status.value,
        feature_id=feature.feature_id,
        epic_id=epic_id,
        payload=feature.model_dump(mode="json"),
    )


def _task_item(task: QATask) -> ReviewQueueItem:
    reviewer = QA_LEAD_REVIEWER if task.lane == "BLOCK" else task.assignee
    return ReviewQueueItem(
        target_type="task",
        target_id=task.task_id,
        title=task.title,
        reviewer=reviewer,
        lane=task.lane,
        review_status=task.review_status.value,
        feature_id=task.feature_id,
        epic_id=task.epic_id,
        payload=task.model_dump(mode="json"),
    )


def _test_case_item(test_case: TestCase, task: QATask | None) -> ReviewQueueItem:
    lane = test_case.lane
    reviewer = QA_LEAD_REVIEWER if lane == "BLOCK" else task.assignee if task else QA_LEAD_REVIEWER
    return ReviewQueueItem(
        target_type="test_case",
        target_id=test_case.test_case_id,
        title=test_case.title,
        reviewer=reviewer,
        lane=lane,
        review_status=test_case.review_status.value,
        feature_id=task.feature_id if task else None,
        epic_id=task.epic_id if task else None,
        payload=test_case.model_dump(mode="json"),
    )


def _group_queue_items(items: list[ReviewQueueItem]) -> list[ReviewQueueGroup]:
    grouped: dict[tuple[str, str | None, str | None], list[ReviewQueueItem]] = defaultdict(list)
    for item in items:
        grouped[(item.reviewer, item.feature_id, item.epic_id)].append(item)

    groups: list[ReviewQueueGroup] = []
    for (reviewer, feature_id, epic_id), group_items in sorted(
        grouped.items(),
        key=lambda entry: tuple(_sort_value(value) for value in entry[0]),
    ):
        groups.append(
            ReviewQueueGroup(
                group_id=_group_id(reviewer, feature_id, epic_id),
                reviewer=reviewer,
                feature_id=feature_id,
                epic_id=epic_id,
                item_count=len(group_items),
                items=sorted(group_items, key=lambda item: item.target_id),
            )
        )
    return groups


def _group_id(reviewer: str, feature_id: str | None, epic_id: str | None) -> str:
    parts: list[tuple[str, Any]] = [
        ("reviewer", reviewer),
        ("feature", feature_id or "none"),
        ("epic", epic_id or "none"),
    ]
    return "|".join(f"{key}:{value}" for key, value in parts)


def _sort_value(value: str | None) -> str:
    return value or ""
