from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.domain.models import (
    AgentBJob,
    AgentRun,
    Epic,
    Feature,
    GDDDocument,
    GDDSection,
    HIL0Resolution,
    HIL0Question,
    Project,
    QATask,
    ReviewDecision,
    RiskEvent,
    Run,
    Story,
    SyncEvent,
    SyncStatus,
    TestCase,
    ValidationIssue,
    utc_now,
)

QA_TASK_PATCH_FIELDS = {
    "title",
    "description",
    "assignee",
    "priority",
    "priority_justification",
    "estimate",
    "source_sections",
    "status",
    "confidence",
    "dedup_flag",
    "cross_cutting_flag",
}


class WorkflowRepository(ABC):
    @abstractmethod
    def upsert_project(self, project: Project) -> Project: ...

    @abstractmethod
    def get_project(self, project_id: str) -> Project | None: ...

    @abstractmethod
    def list_projects(self) -> list[Project]: ...

    @abstractmethod
    def create_run(self, run: Run) -> Run: ...

    @abstractmethod
    def update_run(self, run: Run) -> Run: ...

    @abstractmethod
    def list_runs(self) -> list[Run]: ...

    @abstractmethod
    def get_run(self, run_id: str) -> Run | None: ...

    @abstractmethod
    def create_gdd_document(self, document: GDDDocument) -> GDDDocument: ...

    @abstractmethod
    def get_gdd_document(self, document_id: str) -> GDDDocument | None: ...

    @abstractmethod
    def list_gdd_documents(self, project_id: str) -> list[GDDDocument]: ...

    @abstractmethod
    def get_latest_gdd_document(self, project_id: str) -> GDDDocument | None: ...

    @abstractmethod
    def next_gdd_version_id(self, project_id: str) -> str: ...

    @abstractmethod
    def add_sections(self, sections: list[GDDSection]) -> list[GDDSection]: ...

    @abstractmethod
    def list_sections(self, run_id: str) -> list[GDDSection]: ...

    @abstractmethod
    def add_hil0_questions(self, questions: list[HIL0Question]) -> list[HIL0Question]: ...

    @abstractmethod
    def list_hil0_questions(self, run_id: str) -> list[HIL0Question]: ...

    @abstractmethod
    def add_hil0_resolution(self, resolution: HIL0Resolution) -> HIL0Resolution: ...

    @abstractmethod
    def add_hil0_resolutions(self, resolutions: list[HIL0Resolution]) -> list[HIL0Resolution]: ...

    @abstractmethod
    def list_hil0_resolutions(self, run_id: str) -> list[HIL0Resolution]: ...

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
    def add_risk_events(self, events: list[RiskEvent]) -> list[RiskEvent]: ...

    @abstractmethod
    def list_risk_events(self, run_id: str) -> list[RiskEvent]: ...

    @abstractmethod
    def add_review_decision(self, decision: ReviewDecision) -> ReviewDecision: ...

    @abstractmethod
    def list_review_decisions(self, run_id: str) -> list[ReviewDecision]: ...

    @abstractmethod
    def add_agent_run(self, agent_run: AgentRun) -> AgentRun: ...

    @abstractmethod
    def list_agent_runs(self, run_id: str) -> list[AgentRun]: ...

    @abstractmethod
    def add_agent_b_jobs(self, jobs: list[AgentBJob]) -> list[AgentBJob]: ...

    @abstractmethod
    def update_agent_b_job(self, job: AgentBJob) -> AgentBJob: ...

    @abstractmethod
    def list_agent_b_jobs(self, run_id: str) -> list[AgentBJob]: ...

    @abstractmethod
    def get_agent_b_job(self, job_id: str) -> AgentBJob | None: ...

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
        self.gdd_documents: dict[str, GDDDocument] = {}
        self.sections: dict[str, list[GDDSection]] = {}
        self.hil0_questions: dict[str, list[HIL0Question]] = {}
        self.hil0_resolutions: dict[str, list[HIL0Resolution]] = {}
        self.features: dict[str, list[Feature]] = {}
        self.epics: dict[str, list[Epic]] = {}
        self.stories: dict[str, list[Story]] = {}
        self.tasks: dict[str, list[QATask]] = {}
        self.test_cases: dict[str, list[TestCase]] = {}
        self.validation_issues: dict[str, list[ValidationIssue]] = {}
        self.risk_events: dict[str, list[RiskEvent]] = {}
        self.review_decisions: dict[str, list[ReviewDecision]] = {}
        self.agent_runs: dict[str, list[AgentRun]] = {}
        self.agent_b_jobs: dict[str, list[AgentBJob]] = {}
        self.sync_events: dict[str, list[SyncEvent]] = {}

    def upsert_project(self, project: Project) -> Project:
        self.projects[project.id] = project
        return project

    def get_project(self, project_id: str) -> Project | None:
        return self.projects.get(project_id)

    def list_projects(self) -> list[Project]:
        return sorted(self.projects.values(), key=lambda project: project.created_at, reverse=True)

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

    def create_gdd_document(self, document: GDDDocument) -> GDDDocument:
        self.gdd_documents[document.id] = document
        return document

    def get_gdd_document(self, document_id: str) -> GDDDocument | None:
        return self.gdd_documents.get(document_id)

    def list_gdd_documents(self, project_id: str) -> list[GDDDocument]:
        documents = [
            document
            for document in self.gdd_documents.values()
            if document.project_id == project_id
        ]
        return sorted(documents, key=lambda document: _version_number(document.version_id), reverse=True)

    def get_latest_gdd_document(self, project_id: str) -> GDDDocument | None:
        documents = self.list_gdd_documents(project_id)
        return documents[0] if documents else None

    def next_gdd_version_id(self, project_id: str) -> str:
        documents = self.list_gdd_documents(project_id)
        next_number = max((_version_number(document.version_id) for document in documents), default=0) + 1
        return f"v{next_number}"

    def add_sections(self, sections: list[GDDSection]) -> list[GDDSection]:
        if not sections:
            return sections
        self.sections[sections[0].run_id] = sections
        return sections

    def list_sections(self, run_id: str) -> list[GDDSection]:
        return self.sections.get(run_id, [])

    def add_hil0_questions(self, questions: list[HIL0Question]) -> list[HIL0Question]:
        if questions:
            self.hil0_questions[questions[0].run_id] = questions
        return questions

    def list_hil0_questions(self, run_id: str) -> list[HIL0Question]:
        return self.hil0_questions.get(run_id, [])

    def add_hil0_resolution(self, resolution: HIL0Resolution) -> HIL0Resolution:
        return self.add_hil0_resolutions([resolution])[0]

    def add_hil0_resolutions(self, resolutions: list[HIL0Resolution]) -> list[HIL0Resolution]:
        for resolution in resolutions:
            self.hil0_resolutions.setdefault(resolution.run_id, []).append(resolution)
            for question in self.hil0_questions.get(resolution.run_id, []):
                if question.id == resolution.question_id:
                    question.status = "RESOLVED"
                    question.resolved_action = resolution.action
                    break
        return resolutions

    def list_hil0_resolutions(self, run_id: str) -> list[HIL0Resolution]:
        return self.hil0_resolutions.get(run_id, [])

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

    def add_risk_events(self, events: list[RiskEvent]) -> list[RiskEvent]:
        if events:
            self.risk_events.setdefault(events[0].run_id, []).extend(events)
        return events

    def list_risk_events(self, run_id: str) -> list[RiskEvent]:
        return self.risk_events.get(run_id, [])

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

    def add_agent_b_jobs(self, jobs: list[AgentBJob]) -> list[AgentBJob]:
        for job in jobs:
            current = self.agent_b_jobs.setdefault(job.run_id, [])
            existing_index = next(
                (index for index, existing in enumerate(current) if existing.id == job.id),
                None,
            )
            if existing_index is None:
                current.append(job)
            else:
                current[existing_index] = job
        return jobs

    def update_agent_b_job(self, job: AgentBJob) -> AgentBJob:
        current = self.agent_b_jobs.setdefault(job.run_id, [])
        for index, existing in enumerate(current):
            if existing.id == job.id:
                current[index] = job.model_copy(update={"updated_at": utc_now()})
                return current[index]
        current.append(job)
        return job

    def list_agent_b_jobs(self, run_id: str) -> list[AgentBJob]:
        jobs = self.agent_b_jobs.get(run_id, [])
        return sorted(jobs, key=lambda job: (job.started_at or job.created_at, job.id))

    def get_agent_b_job(self, job_id: str) -> AgentBJob | None:
        for jobs in self.agent_b_jobs.values():
            for job in jobs:
                if job.id == job_id:
                    return job
        return None

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
        if decision.target_type == "epic":
            epic = _apply_to_collection(
                self.epics.get(decision.run_id, []),
                "epic_id",
                decision.target_id,
                decision.decision,
            )
            if epic is not None:
                for feature in self.features.get(decision.run_id, []):
                    if feature.feature_id in epic.feature_ids:
                        feature.review_status = decision.decision
                for story in self.stories.get(decision.run_id, []):
                    if story.epic_id == epic.epic_id:
                        story.review_status = decision.decision
            return

        collections: dict[str, tuple[list[Any], str]] = {
            "feature": (self.features.get(decision.run_id, []), "feature_id"),
            "test_case": (self.test_cases.get(decision.run_id, []), "test_case_id"),
            "story": (self.stories.get(decision.run_id, []), "story_id"),
        }
        if decision.target_type == "task":
            _apply_task_decision(self.tasks.get(decision.run_id, []), decision)
            return

        collection = collections.get(decision.target_type)
        if collection is None:
            return
        _apply_to_collection(collection[0], collection[1], decision.target_id, decision.decision)


def _version_number(version_id: str) -> int:
    if version_id.startswith("v") and version_id[1:].isdigit():
        return int(version_id[1:])
    return 0


def _apply_to_collection(
    collection: list[Any],
    public_id_field: str,
    target_id: str,
    decision: Any,
) -> Any | None:
    for item in collection:
        if item.id == target_id or getattr(item, public_id_field, None) == target_id:
            item.review_status = decision
            return item
    return None


def _apply_task_decision(collection: list[QATask], decision: ReviewDecision) -> QATask | None:
    patch = _task_patch_from_decision(decision)
    for index, task in enumerate(collection):
        if task.id == decision.target_id or task.task_id == decision.target_id:
            payload = {
                **task.model_dump(mode="python"),
                **patch,
                "review_status": decision.decision,
            }
            updated = QATask.model_validate(payload)
            collection[index] = updated
            return updated
    return None


def _task_patch_from_decision(decision: ReviewDecision) -> dict[str, Any]:
    if not decision.patch:
        return {}

    raw_patch = decision.patch.get("task", decision.patch)
    if not isinstance(raw_patch, dict):
        return {}

    return {
        key: value
        for key, value in raw_patch.items()
        if key in QA_TASK_PATCH_FIELDS and value is not None
    }
