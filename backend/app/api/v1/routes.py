from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException

from app.api.v1.dependencies import pipeline_dependency, repository_dependency, settings_dependency
from app.config import Settings
from app.domain.models import (
    AgentBJobRetryRequest,
    DemoRunRequest,
    EpicMergeRequest,
    EpicPatchRequest,
    EpicSplitRequest,
    HIL2DecisionAction,
    HIL2TaskDecisionRequest,
    HIL0BulkResolutionRequest,
    HIL0Resolution,
    HIL0ResolutionRequest,
    ProjectCreateRequest,
    ReviewDecision,
    ReviewDecisionRequest,
    ReviewStatus,
    S0TriggerRequest,
    S1ContextRequest,
    SignOffRequest,
    utc_now,
)
from app.domain.responses import envelope
from app.domain.qa_roster import QA_MEMBERS
from app.services.agents.factory import SUPPORTED_AI_PROVIDERS
from app.services.pipeline import PipelineConflictError
from app.services.review_queues import build_review_queue

router = APIRouter()

HIL2_ACTION_STATUS = {
    HIL2DecisionAction.APPROVE: ReviewStatus.APPROVED,
    HIL2DecisionAction.REQUEST_EDIT: ReviewStatus.BLOCKED,
    HIL2DecisionAction.REJECT: ReviewStatus.REJECTED,
    HIL2DecisionAction.OVERRIDE_ASSIGNEE: ReviewStatus.NEEDS_REVIEW,
}


@router.get("/health")
def health() -> dict[str, object]:
    settings = settings_dependency()
    return envelope(
        {
            "status": "ok",
            "app_env": settings.app_env,
            "ai_provider": settings.ai_provider,
            "notion_provider": settings.notion_provider,
            "repository_provider": settings.repository_provider,
        }
    )


@router.get("/providers/status")
def get_provider_status() -> dict[str, object]:
    settings = settings_dependency()
    return envelope(
        {
            "ai": {
                "provider": settings.ai_provider,
                "credentials_ready": _ai_credentials_ready(settings),
            },
            "notion": {
                "provider": settings.notion_provider,
                "credentials_ready": _notion_credentials_ready(settings),
            },
            "repository": {
                "provider": settings.repository_provider,
                "credentials_ready": _repository_credentials_ready(settings),
            },
        }
    )


@router.post("/demo-runs")
def create_demo_run(payload: DemoRunRequest) -> dict[str, object]:
    try:
        run = pipeline_dependency().run_demo(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return envelope(run)


@router.post("/projects")
def create_project(payload: ProjectCreateRequest) -> dict[str, object]:
    try:
        project = pipeline_dependency().create_project(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return envelope(project)


@router.get("/projects")
def list_projects() -> dict[str, object]:
    return envelope(repository_dependency().list_projects())


@router.get("/projects/{project_id}")
def get_project(project_id: str) -> dict[str, object]:
    return envelope(_require_project(project_id))


@router.get("/projects/{project_id}/gdd-documents")
def get_project_gdd_documents(project_id: str) -> dict[str, object]:
    _require_project(project_id)
    return envelope(repository_dependency().list_gdd_documents(project_id))


@router.get("/runs")
def list_runs() -> dict[str, object]:
    return envelope(repository_dependency().list_runs())


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    run = repository_dependency().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return envelope(run)


@router.post("/runs/trigger")
def trigger_run(payload: S0TriggerRequest) -> dict[str, object]:
    try:
        result = pipeline_dependency().trigger_run(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return envelope(result)


@router.post("/runs/{run_id}/context")
def load_run_context(run_id: str, payload: S1ContextRequest | None = None) -> dict[str, object]:
    try:
        result = pipeline_dependency().load_context(run_id, payload or S1ContextRequest())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return envelope(result)


@router.post("/runs/{run_id}/agent-a")
def run_agent_a(run_id: str) -> dict[str, object]:
    try:
        run = pipeline_dependency().run_agent_a(run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PipelineConflictError as exc:
        _raise_pipeline_conflict(exc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return envelope(run)


@router.post("/runs/{run_id}/agent-b")
def run_agent_b(run_id: str) -> dict[str, object]:
    try:
        run = pipeline_dependency().run_agent_b(run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PipelineConflictError as exc:
        _raise_pipeline_conflict(exc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return envelope(run)


@router.post("/runs/{run_id}/agent-c")
def run_agent_c(run_id: str) -> dict[str, object]:
    try:
        run = pipeline_dependency().run_agent_c(run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PipelineConflictError as exc:
        _raise_pipeline_conflict(exc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return envelope(run)


@router.post("/runs/{run_id}/finalize")
def finalize_run(run_id: str) -> dict[str, object]:
    try:
        run = pipeline_dependency().finalize_run(run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PipelineConflictError as exc:
        _raise_pipeline_conflict(exc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return envelope(run)


# ===========================================================================
# Phase 1.8 — Hierarchical Agent B endpoints.
#
# All eight endpoints below are scaffolding only. Each returns HTTP 501 with
# a `not_implemented` error envelope until the corresponding PipelineService
# method (or repository method, for the read endpoint) lands. See
# backend/PLAN.md "Phase 1.8 - Agent B Hierarchical Decomposition" for the
# target behavior, and backend/TASKS.md for the implementation checklist.
#
# Wiring strategy when implementing:
#   1. Replace `_phase_1_8_not_implemented(...)` with the real service call.
#   2. Catch LookupError -> 404, PipelineConflictError -> 409, ValueError -> 422
#      following the same shape as run_agent_a / run_agent_b above.
#   3. Drop the corresponding TODO comment.
# ===========================================================================


@router.post("/runs/{run_id}/agent-b/epics")
def run_agent_b_epics(run_id: str) -> dict[str, object]:
    """S4.1 — Agent B1 Epic Planner. Advances S3 -> S4.1, runs Sync-A1."""
    # TODO(phase-1.8): wire to pipeline_dependency().run_agent_b_epics(run_id).
    _phase_1_8_not_implemented("/agent-b/epics", "PipelineService.run_agent_b_epics")


@router.post("/runs/{run_id}/agent-b/stories")
def run_agent_b_stories(run_id: str) -> dict[str, object]:
    """S4.2 — Agent B2 Story Planner, fan-out per epic. Advances S4.1 -> S4.2,
    runs Sync-A2 per epic."""
    # TODO(phase-1.8): wire to pipeline_dependency().run_agent_b_stories(run_id).
    _phase_1_8_not_implemented("/agent-b/stories", "PipelineService.run_agent_b_stories")


@router.post("/runs/{run_id}/agent-b/tasks")
def run_agent_b_tasks(run_id: str) -> dict[str, object]:
    """S4.3 — Agent B3 Task Planner, fan-out per story. Advances S4.2 -> S4.3,
    runs V-B3 (incl. cross-story / cross-epic dedup), then Sync-B."""
    # TODO(phase-1.8): wire to pipeline_dependency().run_agent_b_tasks(run_id).
    _phase_1_8_not_implemented("/agent-b/tasks", "PipelineService.run_agent_b_tasks")


@router.post("/runs/{run_id}/agent-b/jobs/{job_id}/retry")
def retry_agent_b_job(
    run_id: str,
    job_id: str,
    payload: AgentBJobRetryRequest | None = None,
) -> dict[str, object]:
    """Retry a single failed/timeout AgentBJob without re-fanning out siblings."""
    # TODO(phase-1.8): wire to pipeline_dependency().retry_agent_b_job(run_id, job_id, payload).
    # Body is currently empty; AgentBJobRetryRequest exists for future fields.
    _ = payload
    _phase_1_8_not_implemented(
        f"/agent-b/jobs/{job_id}/retry", "PipelineService.retry_agent_b_job"
    )


@router.get("/runs/{run_id}/agent-b-jobs")
def list_agent_b_jobs(run_id: str) -> dict[str, object]:
    """List AgentBJob[] for the run. FE <AgentBJobBoard> polls this every 2s
    while any job is non-terminal."""
    # TODO(phase-1.8): wire to repository_dependency().list_agent_b_jobs(run_id).
    _phase_1_8_not_implemented("/agent-b-jobs", "WorkflowRepository.list_agent_b_jobs")


@router.patch("/runs/{run_id}/epics/{epic_id}")
def patch_epic(run_id: str, epic_id: str, payload: EpicPatchRequest) -> dict[str, object]:
    """Lead inline-edit on <EpicReviewPanel> before S4.2. Rejected with 409
    `epic_edit_after_lock` unless current_stage == S4_1_AGENT_B_EPICS."""
    # TODO(phase-1.8): wire to pipeline_dependency().patch_epic(run_id, epic_id, payload).
    _ = payload
    _phase_1_8_not_implemented(
        f"/epics/{epic_id} (PATCH)", "PipelineService.patch_epic"
    )


@router.post("/runs/{run_id}/epics/merge")
def merge_epics(run_id: str, payload: EpicMergeRequest) -> dict[str, object]:
    """Merge >=2 epics into one. Validates feature_id coverage exhaustively."""
    # TODO(phase-1.8): wire to pipeline_dependency().merge_epics(run_id, payload).
    _ = payload
    _phase_1_8_not_implemented("/epics/merge", "PipelineService.merge_epics")


@router.post("/runs/{run_id}/epics/split")
def split_epic(run_id: str, payload: EpicSplitRequest) -> dict[str, object]:
    """Split one epic into N>=2 new epics. Every original feature_id must
    appear in exactly one split or 409 `epic_edit_feature_coverage` is raised."""
    # TODO(phase-1.8): wire to pipeline_dependency().split_epic(run_id, payload).
    _ = payload
    _phase_1_8_not_implemented("/epics/split", "PipelineService.split_epic")


def _phase_1_8_not_implemented(endpoint_label: str, owner: str) -> None:
    """Helper: return 501 with the standard envelope so clients see a clear
    `not_implemented` error code instead of a generic 500."""
    raise HTTPException(
        status_code=501,
        detail={
            "code": "not_implemented",
            "message": (
                f"Endpoint '{endpoint_label}' is part of Phase 1.8 (Agent B "
                f"hierarchical decomposition) and is not yet implemented. "
                f"Implement '{owner}' to enable it."
            ),
            "details": {"phase": "1.8", "owner": owner},
        },
    )


@router.get("/runs/{run_id}/timeline")
def get_timeline(run_id: str) -> dict[str, object]:
    run = _require_run(run_id)
    return envelope(run.timeline)


@router.get("/runs/{run_id}/coverage")
def get_coverage(run_id: str) -> dict[str, object]:
    try:
        coverage = pipeline_dependency().coverage_report(run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return envelope(coverage)


@router.get("/runs/{run_id}/sections")
def get_sections(run_id: str) -> dict[str, object]:
    _require_run(run_id)
    return envelope(repository_dependency().list_sections(run_id))


@router.get("/runs/{run_id}/hil-0/questions")
def get_hil0_questions(run_id: str) -> dict[str, object]:
    _require_run(run_id)
    return envelope(repository_dependency().list_hil0_questions(run_id))


@router.get("/runs/{run_id}/hil-0/resolutions")
def get_hil0_resolutions(run_id: str) -> dict[str, object]:
    _require_run(run_id)
    return envelope(repository_dependency().list_hil0_resolutions(run_id))


@router.post("/runs/{run_id}/hil-0/resolutions")
def create_hil0_resolution(run_id: str, payload: HIL0ResolutionRequest) -> dict[str, object]:
    _require_run(run_id)
    question_ids = {question.id for question in repository_dependency().list_hil0_questions(run_id)}
    if payload.question_id not in question_ids:
        raise HTTPException(status_code=404, detail="HIL-0 question not found.")
    resolution = repository_dependency().add_hil0_resolution(
        HIL0Resolution(run_id=run_id, **payload.model_dump())
    )
    return envelope(resolution)


@router.post("/runs/{run_id}/hil-0/resolutions/bulk")
def create_hil0_resolutions(run_id: str, payload: HIL0BulkResolutionRequest) -> dict[str, object]:
    _require_run(run_id)
    question_ids = {question.id for question in repository_dependency().list_hil0_questions(run_id)}
    requested_ids = [resolution.question_id for resolution in payload.resolutions]
    missing_ids = sorted(set(requested_ids) - question_ids)
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "HIL-0 question not found.",
                "question_ids": missing_ids,
            },
        )

    duplicate_ids = sorted(
        question_id for question_id, count in Counter(requested_ids).items() if count > 1
    )
    if duplicate_ids:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Duplicate HIL-0 question resolution.",
                "question_ids": duplicate_ids,
            },
        )

    resolutions = [
        HIL0Resolution(run_id=run_id, **resolution.model_dump())
        for resolution in payload.resolutions
    ]
    return envelope(repository_dependency().add_hil0_resolutions(resolutions))


@router.get("/runs/{run_id}/features")
def get_features(run_id: str) -> dict[str, object]:
    _require_run(run_id)
    return envelope(repository_dependency().list_features(run_id))


@router.get("/runs/{run_id}/epics")
def get_epics(run_id: str) -> dict[str, object]:
    _require_run(run_id)
    return envelope(repository_dependency().list_epics(run_id))


@router.get("/runs/{run_id}/stories")
def get_stories(run_id: str) -> dict[str, object]:
    _require_run(run_id)
    return envelope(repository_dependency().list_stories(run_id))


@router.get("/runs/{run_id}/tasks")
def get_tasks(run_id: str) -> dict[str, object]:
    _require_run(run_id)
    return envelope(repository_dependency().list_tasks(run_id))


@router.get("/runs/{run_id}/test-cases")
def get_test_cases(run_id: str) -> dict[str, object]:
    _require_run(run_id)
    return envelope(repository_dependency().list_test_cases(run_id))


@router.get("/runs/{run_id}/validation-issues")
def get_validation_issues(run_id: str) -> dict[str, object]:
    _require_run(run_id)
    return envelope(repository_dependency().list_validation_issues(run_id))


@router.get("/runs/{run_id}/risk-events")
def get_risk_events(run_id: str) -> dict[str, object]:
    _require_run(run_id)
    return envelope(repository_dependency().list_risk_events(run_id))


@router.get("/runs/{run_id}/sync-events")
def get_sync_events(run_id: str) -> dict[str, object]:
    _require_run(run_id)
    return envelope(repository_dependency().list_sync_events(run_id))


@router.get("/runs/{run_id}/agent-runs")
def get_agent_runs(run_id: str) -> dict[str, object]:
    _require_run(run_id)
    return envelope(repository_dependency().list_agent_runs(run_id))


@router.get("/runs/{run_id}/review-decisions")
def get_review_decisions(run_id: str) -> dict[str, object]:
    _require_run(run_id)
    return envelope(repository_dependency().list_review_decisions(run_id))


@router.get("/runs/{run_id}/review-queues/{hil_tier}")
def get_review_queue(run_id: str, hil_tier: str) -> dict[str, object]:
    _require_run(run_id)
    try:
        queue = build_review_queue(repository_dependency(), run_id, hil_tier)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return envelope(queue)


@router.post("/review-decisions")
def create_review_decision(payload: ReviewDecisionRequest) -> dict[str, object]:
    _require_run(payload.run_id)
    decision = repository_dependency().add_review_decision(ReviewDecision(**payload.model_dump()))
    return envelope(decision)


@router.post("/runs/{run_id}/hil-2/tasks/{task_id}/decision")
def create_hil2_task_decision(
    run_id: str,
    task_id: str,
    payload: HIL2TaskDecisionRequest,
) -> dict[str, object]:
    _require_run(run_id)
    _require_task(run_id, task_id)
    _validate_hil2_task_decision(payload)
    decision = repository_dependency().add_review_decision(
        ReviewDecision(
            run_id=run_id,
            target_type="task",
            target_id=task_id,
            decision=HIL2_ACTION_STATUS[payload.action],
            reviewer=payload.reviewer,
            comment=payload.comment,
            patch=_hil2_decision_patch(payload),
        )
    )
    return envelope(
        {
            "decision": decision,
            "task": _require_task(run_id, task_id),
        }
    )


@router.post("/runs/{run_id}/sync-replay")
def replay_sync(run_id: str) -> dict[str, object]:
    _require_run(run_id)
    replayed = repository_dependency().replay_failed_sync_events(run_id)
    return envelope({"replayed_count": len(replayed), "events": replayed})


@router.post("/runs/{run_id}/sign-off")
def sign_off_run(run_id: str, payload: SignOffRequest) -> dict[str, object]:
    run = _require_run(run_id)
    signed_off_at = utc_now()
    run.signed_off_by = payload.reviewer
    run.signed_off_at = signed_off_at
    run.coverage_report = {
        **run.coverage_report,
        "sign_off": {
            "signed_off": True,
            "signed_off_by": payload.reviewer,
            "signed_off_at": signed_off_at.isoformat(),
        },
    }
    return envelope(repository_dependency().update_run(run))


def _require_run(run_id: str):
    run = repository_dependency().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run


def _require_project(project_id: str):
    project = repository_dependency().get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def _require_task(run_id: str, task_id: str):
    task = next(
        (
            task
            for task in repository_dependency().list_tasks(run_id)
            if task.id == task_id or task.task_id == task_id
        ),
        None,
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task


def _validate_hil2_task_decision(payload: HIL2TaskDecisionRequest) -> None:
    task_patch = payload.patch.to_task_update() if payload.patch else {}
    assignee = payload.assignee or task_patch.get("assignee")
    if assignee is not None and assignee not in QA_MEMBERS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_assignee_override",
                "message": "Assignee override must be a seeded QA member.",
                "details": {
                    "assignee": assignee,
                    "allowed_assignees": sorted(QA_MEMBERS),
                },
            },
        )


def _hil2_decision_patch(payload: HIL2TaskDecisionRequest) -> dict[str, object]:
    task_patch = payload.patch.to_task_update() if payload.patch else {}
    stored_patch: dict[str, object] = {
        "hil_tier": "HIL-2",
        "action": payload.action.value,
    }

    if payload.action == HIL2DecisionAction.REQUEST_EDIT:
        if task_patch:
            stored_patch["requested_changes"] = task_patch
        return stored_patch

    if payload.action == HIL2DecisionAction.OVERRIDE_ASSIGNEE:
        task_patch = {**task_patch, "assignee": payload.assignee or task_patch["assignee"]}

    if task_patch:
        stored_patch["task"] = task_patch
    return stored_patch


def _raise_pipeline_conflict(exc: PipelineConflictError) -> None:
    raise HTTPException(
        status_code=409,
        detail={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
    ) from exc


def _ai_credentials_ready(settings: Settings) -> bool:
    provider = settings.ai_provider.lower()
    if provider == "mock":
        return True
    if provider in {"openai", "real"}:
        return bool(settings.openai_api_key)
    return provider in SUPPORTED_AI_PROVIDERS


def _notion_credentials_ready(settings: Settings) -> bool:
    if settings.notion_provider.lower() == "mock":
        return True
    return bool(settings.notion_token)


def _repository_credentials_ready(settings: Settings) -> bool:
    provider = settings.repository_provider.lower()
    if provider == "memory":
        return True
    if provider == "supabase":
        return bool(settings.supabase_url and settings.supabase_service_role_key)
    return False
