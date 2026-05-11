from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.v1.dependencies import pipeline_dependency, repository_dependency, settings_dependency
from app.config import Settings
from app.domain.models import (
    DemoRunRequest,
    HIL0Resolution,
    HIL0ResolutionRequest,
    ProjectCreateRequest,
    ReviewDecision,
    ReviewDecisionRequest,
    S0TriggerRequest,
    S1ContextRequest,
    SignOffRequest,
    utc_now,
)
from app.domain.responses import envelope
from app.services.agents.factory import SUPPORTED_AI_PROVIDERS
from app.services.review_queues import build_review_queue

router = APIRouter()


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
