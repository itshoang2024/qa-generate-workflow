from __future__ import annotations

from typing import Any, TypeVar

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
from app.repositories.workflow_repository import WorkflowRepository

ModelT = TypeVar("ModelT")


class SupabaseWorkflowRepository(WorkflowRepository):
    """Supabase-backed repository for the same contracts as the in-memory demo store."""

    def __init__(self, url: str, service_role_key: str) -> None:
        try:
            from supabase import create_client
        except ImportError as exc:
            raise RuntimeError("Install the 'supabase' package to use Supabase storage.") from exc

        self.client = create_client(url, service_role_key)

    def upsert_project(self, project: Project) -> Project:
        self._upsert("projects", project)
        return project

    def create_run(self, run: Run) -> Run:
        self._insert("runs", run)
        return run

    def update_run(self, run: Run) -> Run:
        updated = run.model_copy(update={"updated_at": utc_now()})
        self.client.table("runs").update(self._dump(updated)).eq("id", run.id).execute()
        return updated

    def list_runs(self) -> list[Run]:
        rows = self.client.table("runs").select("*").order("created_at", desc=True).execute().data
        return [Run.model_validate(row) for row in rows]

    def get_run(self, run_id: str) -> Run | None:
        rows = self.client.table("runs").select("*").eq("id", run_id).execute().data
        return Run.model_validate(rows[0]) if rows else None

    def add_sections(self, sections: list[GDDSection]) -> list[GDDSection]:
        self._replace_run_rows("gdd_sections", sections)
        return sections

    def list_sections(self, run_id: str) -> list[GDDSection]:
        return self._list_run_rows("gdd_sections", run_id, GDDSection)

    def set_features(self, run_id: str, features: list[Feature]) -> list[Feature]:
        self._replace_run_rows("features", features, run_id)
        return features

    def list_features(self, run_id: str) -> list[Feature]:
        return self._list_run_rows("features", run_id, Feature)

    def set_epics(self, run_id: str, epics: list[Epic]) -> list[Epic]:
        self._replace_run_rows("epics", epics, run_id)
        return epics

    def list_epics(self, run_id: str) -> list[Epic]:
        return self._list_run_rows("epics", run_id, Epic)

    def set_stories(self, run_id: str, stories: list[Story]) -> list[Story]:
        self._replace_run_rows("stories", stories, run_id)
        return stories

    def list_stories(self, run_id: str) -> list[Story]:
        return self._list_run_rows("stories", run_id, Story)

    def set_tasks(self, run_id: str, tasks: list[QATask]) -> list[QATask]:
        self._replace_run_rows("qa_tasks", tasks, run_id)
        return tasks

    def list_tasks(self, run_id: str) -> list[QATask]:
        return self._list_run_rows("qa_tasks", run_id, QATask)

    def set_test_cases(self, run_id: str, test_cases: list[TestCase]) -> list[TestCase]:
        self._replace_run_rows("test_cases", test_cases, run_id)
        return test_cases

    def list_test_cases(self, run_id: str) -> list[TestCase]:
        return self._list_run_rows("test_cases", run_id, TestCase)

    def add_validation_issues(self, issues: list[ValidationIssue]) -> list[ValidationIssue]:
        self._bulk_insert("validation_issues", issues)
        return issues

    def list_validation_issues(self, run_id: str) -> list[ValidationIssue]:
        return self._list_run_rows("validation_issues", run_id, ValidationIssue)

    def add_review_decision(self, decision: ReviewDecision) -> ReviewDecision:
        self._insert("review_decisions", decision)
        return decision

    def list_review_decisions(self, run_id: str) -> list[ReviewDecision]:
        return self._list_run_rows("review_decisions", run_id, ReviewDecision)

    def add_agent_run(self, agent_run: AgentRun) -> AgentRun:
        self._insert("agent_runs", agent_run)
        return agent_run

    def list_agent_runs(self, run_id: str) -> list[AgentRun]:
        return self._list_run_rows("agent_runs", run_id, AgentRun)

    def add_sync_events(self, events: list[SyncEvent]) -> list[SyncEvent]:
        self._bulk_insert("sync_events", events)
        return events

    def list_sync_events(self, run_id: str) -> list[SyncEvent]:
        return self._list_run_rows("sync_events", run_id, SyncEvent)

    def replay_failed_sync_events(self, run_id: str) -> list[SyncEvent]:
        events = self.list_sync_events(run_id)
        replayed: list[SyncEvent] = []
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
                self.client.table("sync_events").update(self._dump(updated)).eq("id", event.id).execute()
                replayed.append(updated)
        return replayed

    def _insert(self, table: str, model: Any) -> None:
        self.client.table(table).insert(self._dump(model)).execute()

    def _bulk_insert(self, table: str, models: list[Any]) -> None:
        if models:
            self.client.table(table).insert([self._dump(model) for model in models]).execute()

    def _upsert(self, table: str, model: Any) -> None:
        self.client.table(table).upsert(self._dump(model), on_conflict="id").execute()

    def _replace_run_rows(self, table: str, models: list[Any], run_id: str | None = None) -> None:
        target_run_id = run_id or (models[0].run_id if models else None)
        if target_run_id:
            self.client.table(table).delete().eq("run_id", target_run_id).execute()
        self._bulk_insert(table, models)

    def _list_run_rows(self, table: str, run_id: str, model_type: type[ModelT]) -> list[ModelT]:
        rows = self.client.table(table).select("*").eq("run_id", run_id).execute().data
        return [model_type.model_validate(row) for row in rows]

    def _dump(self, model: Any) -> dict[str, Any]:
        return model.model_dump(mode="json")

