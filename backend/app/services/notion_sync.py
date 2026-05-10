from __future__ import annotations

from app.domain.models import Epic, QATask, Story, SyncEvent, TestCase


class MockNotionSyncClient:
    def upsert_epic(self, epic: Epic) -> SyncEvent:
        return SyncEvent(
            run_id=epic.run_id,
            target_type="epic",
            target_id=epic.epic_id,
            external_id=epic.external_id,
            action="upsert",
            payload={
                "database": "Epic",
                "properties": {
                    "Title": epic.title,
                    "Feature IDs": epic.feature_ids,
                    "external_id": epic.external_id,
                },
            },
        )

    def upsert_story(self, story: Story) -> SyncEvent:
        return SyncEvent(
            run_id=story.run_id,
            target_type="story",
            target_id=story.story_id,
            external_id=story.external_id,
            action="upsert",
            payload={
                "database": "Story",
                "properties": {
                    "Title": story.title,
                    "Epic": story.epic_id,
                    "Feature": story.feature_id,
                    "external_id": story.external_id,
                },
            },
        )

    def upsert_task(self, task: QATask, feature_name: str) -> SyncEvent:
        return SyncEvent(
            run_id=task.run_id,
            target_type="task",
            target_id=task.task_id,
            external_id=task.external_id,
            action="upsert",
            payload={
                "database": "Task",
                "properties": {
                    "Task title": task.title,
                    "Description": task.description,
                    "Feature name": feature_name,
                    "Epic / Story": {"epic_id": task.epic_id, "story_id": task.story_id},
                    "Priority": task.priority,
                    "Estimate": task.estimate,
                    "Suggested assignee": task.assignee,
                    "Status": task.status,
                    "Due date": None,
                    "external_id": task.external_id,
                    "Source sections": task.source_sections,
                    "Confidence": task.confidence,
                },
            },
        )

    def upsert_test_case(self, test_case: TestCase) -> SyncEvent:
        return SyncEvent(
            run_id=test_case.run_id,
            target_type="test_case",
            target_id=test_case.test_case_id,
            external_id=test_case.external_id,
            action="upsert",
            payload={
                "database": "Test Case",
                "properties": {
                    "Title": test_case.title,
                    "Type": test_case.type,
                    "Category": test_case.category,
                    "Priority": test_case.priority,
                    "Related task": test_case.related_task_id,
                    "Preconditions": test_case.preconditions,
                    "Steps": test_case.steps,
                    "Expected result": test_case.expected_result,
                    "Source sections": test_case.source_sections,
                    "external_id": test_case.external_id,
                    "Status": test_case.status,
                },
            },
        )

