from pathlib import Path

import pytest

from app.domain.models import DemoRunRequest, RunStatus
from app.repositories.workflow_repository import InMemoryWorkflowRepository
from app.services.pipeline import PipelineService


def test_demo_pipeline_generates_complete_execution_plan() -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace_root = project_root.parent
    gdd_path = workspace_root / "GDD Sample_Snake Escape.docx"
    if not gdd_path.exists():
        pytest.skip("Root-level Snake Escape GDD is not available.")

    repository = InMemoryWorkflowRepository()
    service = PipelineService(
        repository=repository,
        fixture_path=project_root / "data" / "snake_escape_fixture.json",
        snake_gdd_path=gdd_path,
    )

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

