from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models import Epic, QATask, Story, SyncEvent, TestCase


class NotionSyncClient(ABC):
    @abstractmethod
    def upsert_epic(self, epic: Epic) -> SyncEvent: ...

    @abstractmethod
    def upsert_story(self, story: Story) -> SyncEvent: ...

    @abstractmethod
    def upsert_task(self, task: QATask, feature_name: str) -> SyncEvent: ...

    @abstractmethod
    def upsert_test_case(self, test_case: TestCase) -> SyncEvent: ...

    def upsert_epics_batch(self, epics: list[Epic]) -> list[SyncEvent]:
        return [self.upsert_epic(epic) for epic in epics]

    def upsert_stories_for_epic(self, epic: Epic, stories: list[Story]) -> list[SyncEvent]:
        _ = epic
        return [self.upsert_story(story) for story in stories]
