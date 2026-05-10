from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.v1.dependencies import pipeline_dependency, repository_dependency, settings_dependency
from app.domain.models import DemoRunRequest, ReviewDecision, ReviewDecisionRequest
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


@router.get("/runs")
def list_runs() -> dict[str, object]:
    return envelope(repository_dependency().list_runs())


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    run = repository_dependency().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return envelope(run)


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

