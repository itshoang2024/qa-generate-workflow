from pathlib import Path

import pytest

from app.domain.models import (
    DemoRunRequest,
    GDDDescriptionStatus,
    PipelineStage,
    RunStatus,
    S0TriggerRequest,
    S1ContextRequest,
)
from app.repositories.workflow_repository import InMemoryWorkflowRepository
from app.services.pipeline import PipelineService


def _snake_gdd_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "GDD_Sample_Snake_Escape.docx"


def _pipeline_service(repository: InMemoryWorkflowRepository, gdd_path: Path) -> PipelineService:
    project_root = Path(__file__).resolve().parents[2]
    return PipelineService(
        repository=repository,
        fixture_path=project_root / "data" / "snake_escape_fixture.json",
        snake_gdd_path=gdd_path,
    )


def test_demo_pipeline_generates_complete_execution_plan() -> None:
    gdd_path = _snake_gdd_path()
    if not gdd_path.exists():
        pytest.skip("Root-level Snake Escape GDD is not available.")

    repository = InMemoryWorkflowRepository()
    service = _pipeline_service(repository, gdd_path)

    run = service.run_demo(DemoRunRequest())

    assert run.status == RunStatus.COMPLETED
    assert repository.list_sections(run.id)
    assert len(repository.list_features(run.id)) == 8
    assert len(repository.list_tasks(run.id)) == 11
    assert len(repository.list_test_cases(run.id)) == 44
    assert repository.list_sync_events(run.id)
    assert run.coverage_report["task_count"] == 11
    assert run.coverage_report["test_case_count"] == 44
    assert repository.list_validation_issues(run.id)


def test_s0_trigger_creates_run_without_loading_context() -> None:
    gdd_path = _snake_gdd_path()
    if not gdd_path.exists():
        pytest.skip("Root-level Snake Escape GDD is not available.")

    repository = InMemoryWorkflowRepository()
    service = _pipeline_service(repository, gdd_path)

    result = service.trigger_run(
        S0TriggerRequest(project_name="S0 Only Game", gdd_file=str(gdd_path))
    )
    run = repository.get_run(result["run_id"])

    assert result["mode"] == "NEW_GAME"
    assert run is not None
    assert run.current_stage == PipelineStage.S0_TRIGGER
    assert run.session_memory["context_loaded"] is False
    assert repository.list_sections(run.id) == []
    assert repository.list_gdd_documents(run.project_id) == []


def test_s1_context_loader_registers_versioned_gdd_documents_and_delta() -> None:
    gdd_path = _snake_gdd_path()
    if not gdd_path.exists():
        pytest.skip("Root-level Snake Escape GDD is not available.")

    repository = InMemoryWorkflowRepository()
    service = _pipeline_service(repository, gdd_path)

    first_trigger = service.trigger_run(
        S0TriggerRequest(project_name="Versioned Game", gdd_file=str(gdd_path))
    )
    first_context = service.load_context(
        first_trigger["run_id"],
        S1ContextRequest(description="Initial playable Snake Escape GDD."),
    )
    first_document = first_context["gdd_document"]
    first_questions = repository.list_hil0_questions(first_trigger["run_id"])

    second_trigger = service.trigger_run(
        S0TriggerRequest(project_id=first_trigger["project_id"], gdd_file=str(gdd_path))
    )
    second_context = service.load_context(second_trigger["run_id"], S1ContextRequest())
    second_document = second_context["gdd_document"]
    second_run = repository.get_run(second_trigger["run_id"])

    assert first_document.version_id == "v1"
    assert first_document.description_status == GDDDescriptionStatus.USER_PROVIDED
    assert first_questions
    assert second_trigger["mode"] == "DELTA"
    assert second_document.version_id == "v2"
    assert second_document.parent_document_id == first_document.id
    assert second_document.description is None
    assert second_document.description_status == GDDDescriptionStatus.PENDING
    assert second_context["delta_report"]["status"] == "READY"
    assert set(second_context["delta_report"]["buckets"]) == {
        "NEW",
        "MODIFIED",
        "UNCHANGED",
        "REMOVED",
    }
    assert second_run is not None
    assert second_run.gdd_document_id == second_document.id
    assert second_run.source_version_id == "v2"
    assert [doc.version_id for doc in repository.list_gdd_documents(first_trigger["project_id"])] == [
        "v2",
        "v1",
    ]
