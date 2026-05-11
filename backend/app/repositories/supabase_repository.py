from __future__ import annotations

from typing import Any, TypeVar

import httpx

from app.domain.models import (
    AgentRun,
    Epic,
    Feature,
    GDDDocument,
    GDDSection,
    HIL0Question,
    HIL0Resolution,
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
from app.repositories.workflow_repository import WorkflowRepository

ModelT = TypeVar("ModelT")
QA_TASK_OPTIONAL_COMPAT_COLUMNS = {"priority_justification", "delta_status"}
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


class SupabaseWorkflowRepository(WorkflowRepository):
    """Supabase-backed repository for the same contracts as the in-memory demo store."""

    def __init__(self, url: str, service_role_key: str) -> None:
        try:
            from supabase import create_client
        except ImportError as exc:
            raise RuntimeError("Install the 'supabase' package to use Supabase storage.") from exc

        self.client = create_client(url, service_role_key, _build_supabase_client_options())

    def upsert_project(self, project: Project) -> Project:
        self._upsert("projects", project)
        return project

    def get_project(self, project_id: str) -> Project | None:
        rows = self.client.table("projects").select("*").eq("id", project_id).execute().data
        return Project.model_validate(rows[0]) if rows else None

    def list_projects(self) -> list[Project]:
        rows = self.client.table("projects").select("*").order("created_at", desc=True).execute().data
        return [Project.model_validate(row) for row in rows]

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

    def create_gdd_document(self, document: GDDDocument) -> GDDDocument:
        self._insert("gdd_documents", document)
        return document

    def get_gdd_document(self, document_id: str) -> GDDDocument | None:
        rows = self.client.table("gdd_documents").select("*").eq("id", document_id).execute().data
        return GDDDocument.model_validate(rows[0]) if rows else None

    def list_gdd_documents(self, project_id: str) -> list[GDDDocument]:
        rows = (
            self.client.table("gdd_documents")
            .select("*")
            .eq("project_id", project_id)
            .execute()
            .data
        )
        documents = [GDDDocument.model_validate(row) for row in rows]
        return sorted(documents, key=lambda document: _version_number(document.version_id), reverse=True)

    def get_latest_gdd_document(self, project_id: str) -> GDDDocument | None:
        documents = self.list_gdd_documents(project_id)
        return documents[0] if documents else None

    def next_gdd_version_id(self, project_id: str) -> str:
        documents = self.list_gdd_documents(project_id)
        next_number = max((_version_number(document.version_id) for document in documents), default=0) + 1
        return f"v{next_number}"

    def add_sections(self, sections: list[GDDSection]) -> list[GDDSection]:
        self._replace_run_rows("gdd_sections", sections)
        return sections

    def list_sections(self, run_id: str) -> list[GDDSection]:
        return self._list_run_rows("gdd_sections", run_id, GDDSection)

    def add_hil0_questions(self, questions: list[HIL0Question]) -> list[HIL0Question]:
        if questions:
            self.client.table("hil0_questions").delete().eq("run_id", questions[0].run_id).execute()
        self._bulk_insert("hil0_questions", questions)
        return questions

    def list_hil0_questions(self, run_id: str) -> list[HIL0Question]:
        return self._list_run_rows("hil0_questions", run_id, HIL0Question)

    def add_hil0_resolution(self, resolution: HIL0Resolution) -> HIL0Resolution:
        return self.add_hil0_resolutions([resolution])[0]

    def add_hil0_resolutions(self, resolutions: list[HIL0Resolution]) -> list[HIL0Resolution]:
        if not resolutions:
            return resolutions

        self._bulk_insert("hil0_resolutions", resolutions)
        question_ids_by_action: dict[str, list[str]] = {}
        for resolution in resolutions:
            question_ids_by_action.setdefault(resolution.action.value, []).append(resolution.question_id)

        for action, question_ids in question_ids_by_action.items():
            self.client.table("hil0_questions").update(
                {
                    "status": "RESOLVED",
                    "resolved_action": action,
                }
            ).in_("id", question_ids).execute()
        return resolutions

    def list_hil0_resolutions(self, run_id: str) -> list[HIL0Resolution]:
        return self._list_run_rows("hil0_resolutions", run_id, HIL0Resolution)

    def set_features(self, run_id: str, features: list[Feature]) -> list[Feature]:
        self._replace_run_rows("features", features, run_id)
        return features

    def list_features(self, run_id: str) -> list[Feature]:
        return self._list_run_rows("features", run_id, Feature)

    def set_epics(self, run_id: str, epics: list[Epic]) -> list[Epic]:
        self._replace_run_rows("epics", epics, run_id, on_conflict="external_id")
        return epics

    def list_epics(self, run_id: str) -> list[Epic]:
        return self._list_run_rows("epics", run_id, Epic)

    def set_stories(self, run_id: str, stories: list[Story]) -> list[Story]:
        self._replace_run_rows("stories", stories, run_id, on_conflict="external_id")
        return stories

    def list_stories(self, run_id: str) -> list[Story]:
        return self._list_run_rows("stories", run_id, Story)

    def set_tasks(self, run_id: str, tasks: list[QATask]) -> list[QATask]:
        self._replace_run_rows("qa_tasks", tasks, run_id, on_conflict="external_id")
        return tasks

    def list_tasks(self, run_id: str) -> list[QATask]:
        return self._list_run_rows("qa_tasks", run_id, QATask)

    def set_test_cases(self, run_id: str, test_cases: list[TestCase]) -> list[TestCase]:
        self._replace_run_rows("test_cases", test_cases, run_id, on_conflict="external_id")
        return test_cases

    def list_test_cases(self, run_id: str) -> list[TestCase]:
        return self._list_run_rows("test_cases", run_id, TestCase)

    def add_validation_issues(self, issues: list[ValidationIssue]) -> list[ValidationIssue]:
        self._bulk_insert("validation_issues", issues)
        return issues

    def list_validation_issues(self, run_id: str) -> list[ValidationIssue]:
        return self._list_run_rows("validation_issues", run_id, ValidationIssue)

    def add_risk_events(self, events: list[RiskEvent]) -> list[RiskEvent]:
        self._bulk_insert("risk_events", events)
        return events

    def list_risk_events(self, run_id: str) -> list[RiskEvent]:
        return self._list_run_rows("risk_events", run_id, RiskEvent)

    def add_review_decision(self, decision: ReviewDecision) -> ReviewDecision:
        self._insert("review_decisions", decision)
        self._apply_review_status(decision)
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

    def _replace_run_rows(
        self,
        table: str,
        models: list[Any],
        run_id: str | None = None,
        *,
        on_conflict: str | None = None,
    ) -> None:
        target_run_id = run_id or (models[0].run_id if models else None)
        if target_run_id:
            self.client.table(table).delete().eq("run_id", target_run_id).execute()
        if not models:
            return
        payload = [self._dump(model) for model in models]
        if on_conflict:
            try:
                self.client.table(table).upsert(payload, on_conflict=on_conflict).execute()
            except Exception as exc:
                if not _can_retry_without_optional_task_columns(table, exc):
                    raise
                legacy_payload = [_without_optional_task_columns(row) for row in payload]
                self.client.table(table).upsert(legacy_payload, on_conflict=on_conflict).execute()
            return
        try:
            self.client.table(table).insert(payload).execute()
        except Exception as exc:
            if not _can_retry_without_optional_task_columns(table, exc):
                raise
            legacy_payload = [_without_optional_task_columns(row) for row in payload]
            self.client.table(table).insert(legacy_payload).execute()

    def _list_run_rows(self, table: str, run_id: str, model_type: type[ModelT]) -> list[ModelT]:
        rows = self.client.table(table).select("*").eq("run_id", run_id).execute().data
        return [model_type.model_validate(row) for row in rows]

    def _dump(self, model: Any) -> dict[str, Any]:
        return model.model_dump(mode="json", exclude={"lane"})

    def _apply_review_status(self, decision: ReviewDecision) -> None:
        if decision.target_type == "epic":
            self._update_review_status("epics", "epic_id", decision.target_id, decision)
            epic = next(
                (
                    epic
                    for epic in self.list_epics(decision.run_id)
                    if epic.id == decision.target_id or epic.epic_id == decision.target_id
                ),
                None,
            )
            if epic is None:
                return
            for feature_id in epic.feature_ids:
                self._update_review_status("features", "feature_id", feature_id, decision)
            self.client.table("stories").update({"review_status": decision.decision.value}).eq(
                "run_id",
                decision.run_id,
            ).eq("epic_id", epic.epic_id).execute()
            return

        mapping = {
            "feature": ("features", "feature_id"),
            "test_case": ("test_cases", "test_case_id"),
            "story": ("stories", "story_id"),
        }
        if decision.target_type == "task":
            self._update_task_from_decision(decision)
            return

        if decision.target_type in mapping:
            table, public_id_field = mapping[decision.target_type]
            self._update_review_status(table, public_id_field, decision.target_id, decision)

    def _update_task_from_decision(self, decision: ReviewDecision) -> None:
        payload = {
            "review_status": decision.decision.value,
            **_task_patch_from_decision(decision),
        }
        self.client.table("qa_tasks").update(payload).eq("run_id", decision.run_id).eq(
            "task_id",
            decision.target_id,
        ).execute()
        self.client.table("qa_tasks").update(payload).eq("run_id", decision.run_id).eq(
            "id",
            decision.target_id,
        ).execute()

    def _update_review_status(
        self,
        table: str,
        public_id_field: str,
        target_id: str,
        decision: ReviewDecision,
    ) -> None:
        payload = {"review_status": decision.decision.value}
        self.client.table(table).update(payload).eq("run_id", decision.run_id).eq(
            public_id_field,
            target_id,
        ).execute()
        self.client.table(table).update(payload).eq("run_id", decision.run_id).eq(
            "id",
            target_id,
        ).execute()


def _version_number(version_id: str) -> int:
    if version_id.startswith("v") and version_id[1:].isdigit():
        return int(version_id[1:])
    return 0


def _can_retry_without_optional_task_columns(table: str, exc: Exception) -> bool:
    if table != "qa_tasks":
        return False
    message = str(exc)
    return (
        "PGRST204" in message
        and "schema cache" in message
        and any(f"'{column}' column" in message for column in QA_TASK_OPTIONAL_COMPAT_COLUMNS)
    )


def _without_optional_task_columns(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if key not in QA_TASK_OPTIONAL_COMPAT_COLUMNS
    }


def _build_supabase_client_options() -> Any:
    from supabase import ClientOptions

    return ClientOptions(
        httpx_client=httpx.Client(
            timeout=httpx.Timeout(120),
            follow_redirects=True,
            http2=False,
        )
    )


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
