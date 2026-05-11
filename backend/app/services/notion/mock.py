from __future__ import annotations

import re

from app.domain.models import Epic, QATask, Story, SyncEvent, TestCase
from app.services.notion import NotionSyncClient


class MockNotionSyncClient(NotionSyncClient):
    def __init__(self) -> None:
        self.page_id_by_external_id: dict[str, str] = {}
        self.epic_page_id_by_epic_id: dict[str, str] = {}
        self.story_page_id_by_story_id: dict[str, str] = {}
        self.task_page_id_by_task_id: dict[str, str] = {}

    def upsert_epic(self, epic: Epic) -> SyncEvent:
        page_id = self._page_id_for(epic.external_id)
        self.epic_page_id_by_epic_id[epic.epic_id] = page_id
        return SyncEvent(
            run_id=epic.run_id,
            target_type="epic",
            target_id=epic.epic_id,
            external_id=epic.external_id,
            action="upsert",
            payload={
                "sync_phase": "Sync-A",
                "database": "Epic",
                "notion_page_id": page_id,
                "properties": {
                    "Title": epic.title,
                    "Feature IDs": epic.feature_ids,
                    "external_id": epic.external_id,
                },
            },
        )

    def upsert_story(self, story: Story) -> SyncEvent:
        page_id = self._page_id_for(story.external_id)
        self.story_page_id_by_story_id[story.story_id] = page_id
        return SyncEvent(
            run_id=story.run_id,
            target_type="story",
            target_id=story.story_id,
            external_id=story.external_id,
            action="upsert",
            payload={
                "sync_phase": "Sync-A",
                "database": "Story",
                "notion_page_id": page_id,
                "properties": {
                    "Title": story.title,
                    "Epic": story.epic_id,
                    "Epic page": self.epic_page_id_by_epic_id.get(story.epic_id),
                    "Feature": story.feature_id,
                    "external_id": story.external_id,
                },
            },
        )

    def upsert_task(self, task: QATask, feature_name: str) -> SyncEvent:
        page_id = self._page_id_for(task.external_id)
        self.task_page_id_by_task_id[task.task_id] = page_id
        return SyncEvent(
            run_id=task.run_id,
            target_type="task",
            target_id=task.task_id,
            external_id=task.external_id,
            action="upsert",
            payload={
                "sync_phase": "Sync-B",
                "database": "Task",
                "notion_page_id": page_id,
                "properties": {
                    "Task title": task.title,
                    "Description": task.description,
                    "Feature name": feature_name,
                    "Epic / Story": {
                        "epic_id": task.epic_id,
                        "epic_page_id": self.epic_page_id_by_epic_id.get(task.epic_id),
                        "story_id": task.story_id,
                        "story_page_id": self.story_page_id_by_story_id.get(task.story_id),
                    },
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
        page_id = self._page_id_for(test_case.external_id)
        return SyncEvent(
            run_id=test_case.run_id,
            target_type="test_case",
            target_id=test_case.test_case_id,
            external_id=test_case.external_id,
            action="upsert",
            payload={
                "sync_phase": "Sync-C",
                "database": "Test Case",
                "notion_page_id": page_id,
                "properties": {
                    "Title": test_case.title,
                    "Type": test_case.type,
                    "Category": test_case.category,
                    "Priority": test_case.priority,
                    "Related task": test_case.related_task_id,
                    "Related task page": self.task_page_id_by_task_id.get(
                        test_case.related_task_id
                    ),
                    "Preconditions": test_case.preconditions,
                    "Steps": test_case.steps,
                    "Expected result": test_case.expected_result,
                    "Source sections": test_case.source_sections,
                    "external_id": test_case.external_id,
                    "Status": test_case.status,
                },
            },
        )

    def _page_id_for(self, external_id: str) -> str:
        if external_id not in self.page_id_by_external_id:
            safe_id = re.sub(r"[^a-zA-Z0-9]+", "_", external_id).strip("_").lower()
            self.page_id_by_external_id[external_id] = f"mock_page_{safe_id}"
        return self.page_id_by_external_id[external_id]
