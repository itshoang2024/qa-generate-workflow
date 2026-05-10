from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.domain.models import (
    AgentRun,
    Epic,
    Feature,
    GDDSection,
    Project,
    QATask,
    ReviewDecision,
    Run,
    Story,
    SyncEvent,
    SyncStatus,
    TestCase,
    ValidationIssue,
    utc_now,
)


class WorkflowRepository(ABC):
    @abstractmethod
    def upsert_project(self, project: Project) -> Project: ...

    @abstractmethod
    def create_run(self, run: Run) -> Run: ...

    @abstractmethod
    def update_run(self, run: Run) -> Run: ...

    @abstractmethod
    def list_runs(self) -> list[Run]: ...

    @abstractmethod
    def get_run(self, run_id: str) -> Run | None: ...

    @abstractmethod
    def add_sections(self, sections: list[GDDSection]) -> list[GDDSection]: ...

    @abstractmethod
    def list_sections(self, run_id: str) -> list[GDDSection]: ...

    @abstractmethod
    def set_features(self, run_id: str, features: list[Feature]) -> list[Feature]: ...

    @abstractmethod
    def list_features(self, run_id: str) -> list[Feature]: ...

    @abstractmethod
    def set_epics(self, run_id: str, epics: list[Epic]) -> list[Epic]: ...

    @abstractmethod
    def list_epics(self, run_id: str) -> list[Epic]: ...

    @abstractmethod
    def set_stories(self, run_id: str, stories: list[Story]) -> list[Story]: ...

    @abstractmethod
    def list_stories(self, run_id: str) -> list[Story]: ...

    @abstractmethod
    def set_tasks(self, run_id: str, tasks: list[QATask]) -> list[QATask]: ...

    @abstractmethod
    def list_tasks(self, run_id: str) -> list[QATask]: ...

    @abstractmethod
    def set_test_cases(self, run_id: str, test_cases: list[TestCase]) -> list[TestCase]: ...

    @abstractmethod
    def list_test_cases(self, run_id: str) -> list[TestCase]: ...

    @abstractmethod
    def add_validation_issues(self, issues: list[ValidationIssue]) -> list[ValidationIssue]: ...

    @abstractmethod
    def list_validation_issues(self, run_id: str) -> list[ValidationIssue]: ...

    @abstractmethod
    def add_review_decision(self, decision: ReviewDecision) -> ReviewDecision: ...

    @abstractmethod
    def list_review_decisions(self, run_id: str) -> list[ReviewDecision]: ...

    @abstractmethod
    def add_agent_run(self, agent_run: AgentRun) -> AgentRun: ...

    @abstractmethod
    def list_agent_runs(self, run_id: str) -> list[AgentRun]: ...

    @abstractmethod
    def add_sync_events(self, events: list[SyncEvent]) -> list[SyncEvent]: ...

    @abstractmethod
    def list_sync_events(self, run_id: str) -> list[SyncEvent]: ...

    @abstractmethod
    def replay_failed_sync_events(self, run_id: str) -> list[SyncEvent]: ...


class InMemoryWorkflowRepository(WorkflowRepository):
    def __init__(self) -> None:
        self.projects: dict[str, Project] = {}
        self.runs: dict[str, Run] = {}
        self.sections: dict[str, list[GDDSection]] = {}
        self.features: dict[str, list[Feature]] = {}
        self.epics: dict[str, list[Epic]] = {}
        self.stories: dict[str, list[Story]] = {}
        self.tasks: dict[str, list[QATask]] = {}
        self.test_cases: dict[str, list[TestCase]] = {}
        self.validation_issues: dict[str, list[ValidationIssue]] = {}
        self.review_decisions: dict[str, list[ReviewDecision]] = {}
        self.agent_runs: dict[str, list[AgentRun]] = {}
        self.sync_events: dict[str, list[SyncEvent]] = {}

    def upsert_project(self, project: Project) -> Project:
        self.projects[project.id] = project
        return project

    def create_run(self, run: Run) -> Run:
        self.runs[run.id] = run
        return run

    def update_run(self, run: Run) -> Run:
        self.runs[run.id] = run.model_copy(update={"updated_at": utc_now()})
        return self.runs[run.id]

    def list_runs(self) -> list[Run]:
        return sorted(self.runs.values(), key=lambda run: run.created_at, reverse=True)

    def get_run(self, run_id: str) -> Run | None:
        return self.runs.get(run_id)

    def add_sections(self, sections: list[GDDSection]) -> list[GDDSection]:
        if not sections:
            return sections
        self.sections[sections[0].run_id] = sections
        return sections

    def list_sections(self, run_id: str) -> list[GDDSection]:
        return self.sections.get(run_id, [])

    def set_features(self, run_id: str, features: list[Feature]) -> list[Feature]:
        self.features[run_id] = features
        return features

    def list_features(self, run_id: str) -> list[Feature]:
        return self.features.get(run_id, [])

    def set_epics(self, run_id: str, epics: list[Epic]) -> list[Epic]:
        self.epics[run_id] = epics
        return epics

    def list_epics(self, run_id: str) -> list[Epic]:
        return self.epics.get(run_id, [])

    def set_stories(self, run_id: str, stories: list[Story]) -> list[Story]:
        self.stories[run_id] = stories
        return stories

    def list_stories(self, run_id: str) -> list[Story]:
        return self.stories.get(run_id, [])

    def set_tasks(self, run_id: str, tasks: list[QATask]) -> list[QATask]:
        self.tasks[run_id] = tasks
        return tasks

    def list_tasks(self, run_id: str) -> list[QATask]:
        return self.tasks.get(run_id, [])

    def set_test_cases(self, run_id: str, test_cases: list[TestCase]) -> list[TestCase]:
        self.test_cases[run_id] = test_cases
        return test_cases

    def list_test_cases(self, run_id: str) -> list[TestCase]:
        return self.test_cases.get(run_id, [])

    def add_validation_issues(self, issues: list[ValidationIssue]) -> list[ValidationIssue]:
        if issues:
            self.validation_issues.setdefault(issues[0].run_id, []).extend(issues)
        return issues

    def list_validation_issues(self, run_id: str) -> list[ValidationIssue]:
        return self.validation_issues.get(run_id, [])

    def add_review_decision(self, decision: ReviewDecision) -> ReviewDecision:
        self.review_decisions.setdefault(decision.run_id, []).append(decision)
        self._apply_review_status(decision)
        return decision

    def list_review_decisions(self, run_id: str) -> list[ReviewDecision]:
        return self.review_decisions.get(run_id, [])

    def add_agent_run(self, agent_run: AgentRun) -> AgentRun:
        self.agent_runs.setdefault(agent_run.run_id, []).append(agent_run)
        return agent_run

    def list_agent_runs(self, run_id: str) -> list[AgentRun]:
        return self.agent_runs.get(run_id, [])

    def add_sync_events(self, events: list[SyncEvent]) -> list[SyncEvent]:
        if events:
            self.sync_events.setdefault(events[0].run_id, []).extend(events)
        return events

    def list_sync_events(self, run_id: str) -> list[SyncEvent]:
        return self.sync_events.get(run_id, [])

    def replay_failed_sync_events(self, run_id: str) -> list[SyncEvent]:
        replayed: list[SyncEvent] = []
        events = self.sync_events.get(run_id, [])
        for event in events:
            if event.status == SyncStatus.FAILED:
                updated = event.model_copy(
                    update={
                        "status": SyncStatus.REPLAYED,
                        "retry_count": event.retry_count + 1,
                        "error": None,
                        "updated_at": utc_now(),
                    }
                )
                events[events.index(event)] = updated
                replayed.append(updated)
        return replayed

    def _apply_review_status(self, decision: ReviewDecision) -> None:
        collections: dict[str, list[Any]] = {
            "feature": self.features.get(decision.run_id, []),
            "task": self.tasks.get(decision.run_id, []),
            "test_case": self.test_cases.get(decision.run_id, []),
            "epic": self.epics.get(decision.run_id, []),
            "story": self.stories.get(decision.run_id, []),
        }
        for item in collections.get(decision.target_type, []):
            public_id = getattr(item, f"{decision.target_type}_id", None)
            if item.id == decision.target_id or public_id == decision.target_id:
                item.review_status = decision.decision

