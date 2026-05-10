from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.v1.dependencies import pipeline_dependency, repository_dependency, settings_dependency
from app.domain.models import (
    DemoRunRequest,
    HIL0Resolution,
    HIL0ResolutionRequest,
    ProjectCreateRequest,
    ReviewDecision,
    ReviewDecisionRequest,
    S0TriggerRequest,
    S1ContextRequest,
)
from app.domain.responses import envelope

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
    run = _require_run(run_id)
    return envelope(run.coverage_report)


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


@router.get("/runs/{run_id}/sync-events")
def get_sync_events(run_id: str) -> dict[str, object]:
    _require_run(run_id)
    return envelope(repository_dependency().list_sync_events(run_id))


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
