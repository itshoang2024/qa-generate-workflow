from pathlib import Path

import pytest

from app.domain.models import (
    AgentBJob,
    AgentBJobStatus,
    AgentBScope,
    AgentRun,
    DemoRunRequest,
    GDDSection,
    GDDDescriptionStatus,
    PipelineStage,
    QATask,
    ReviewDecision,
    RunStatus,
    RunMode,
    S0TriggerRequest,
    S1ContextRequest,
    TestCase as DomainTestCase,
    ReviewStatus,
)
from app.repositories.workflow_repository import InMemoryWorkflowRepository
from app.services.agents import AgentClient
from app.services.agents.mock import MockAgentClient
from app.services.pipeline import PipelineConflictError, PipelineService


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


def test_demo_pipeline_snapshots_hil1_context_for_agent_b() -> None:
    gdd_path = _snake_gdd_path()
    if not gdd_path.exists():
        pytest.skip("Root-level Snake Escape GDD is not available.")

    repository = InMemoryWorkflowRepository()
    service = _pipeline_service(repository, gdd_path)

    run = service.run_demo(DemoRunRequest())
    stored_run = repository.get_run(run.id)
    agent_b_run = next(
        agent_run
        for agent_run in repository.list_agent_runs(run.id)
        if agent_run.stage == PipelineStage.S4_AGENT_B
    )

    assert stored_run is not None
    hil1_context = stored_run.session_memory["hil_1"]
    assert len(hil1_context["approved_feature_ids"]) == 8
    assert set(hil1_context["review_queue_feature_ids"]) == {"F-004", "F-005"}
    assert hil1_context["epic_structure"]["epics"]
    assert agent_b_run.input_snapshot["hil_1"]["approved_feature_ids"] == hil1_context[
        "approved_feature_ids"
    ]
    assert agent_b_run.input_snapshot["hil_1"]["epic_candidate_count"] == len(
        hil1_context["epic_structure"]["epics"]
    )


def test_agent_b_retries_partial_coverage_before_persisting_plan() -> None:
    gdd_path = _snake_gdd_path()
    if not gdd_path.exists():
        pytest.skip("Root-level Snake Escape GDD is not available.")

    repository = InMemoryWorkflowRepository()
    project_root = Path(__file__).resolve().parents[2]
    agent_client = _RetryingAgentBClient(project_root / "data" / "snake_escape_fixture.json")
    service = PipelineService(
        repository=repository,
        fixture_path=project_root / "data" / "snake_escape_fixture.json",
        snake_gdd_path=gdd_path,
        agent_client=agent_client,
    )

    run = service.run_demo(DemoRunRequest(auto_approve=True))
    agent_b_run = _agent_b_run(repository, run.id)

    assert agent_client.plan_attempts == 2
    assert agent_b_run.output_snapshot["attempt_count"] == 2
    assert agent_b_run.output_snapshot["retry_exhausted"] is False
    assert agent_b_run.output_snapshot["attempts"][0]["missing_feature_ids"]
    assert len(repository.list_epics(run.id)) == 5
    assert len(repository.list_tasks(run.id)) == 11


def test_agent_b_blocks_sync_when_coverage_retry_exhausts() -> None:
    gdd_path = _snake_gdd_path()
    if not gdd_path.exists():
        pytest.skip("Root-level Snake Escape GDD is not available.")

    repository = InMemoryWorkflowRepository()
    project_root = Path(__file__).resolve().parents[2]
    agent_client = _AlwaysPartialAgentBClient(
        project_root / "data" / "snake_escape_fixture.json"
    )
    service = PipelineService(
        repository=repository,
        fixture_path=project_root / "data" / "snake_escape_fixture.json",
        snake_gdd_path=gdd_path,
        agent_client=agent_client,
    )

    triggered = service.trigger_run(
        S0TriggerRequest(project_name="Coverage Guard Game", gdd_file=str(gdd_path))
    )
    run_id = triggered["run_id"]
    service.load_context(run_id, S1ContextRequest())
    service.run_agent_a(run_id)
    _approve_hil1_queue(repository, run_id)

    with pytest.raises(PipelineConflictError) as exc:
        service.run_agent_b(run_id)

    stored_run = repository.get_run(run_id)
    agent_b_run = _agent_b_run(repository, run_id)
    issue_codes = {issue.code for issue in repository.list_validation_issues(run_id)}
    risk_codes = {event.code for event in repository.list_risk_events(run_id)}

    assert exc.value.code == "agent_b_coverage_exhausted"
    assert stored_run is not None
    assert stored_run.current_stage == PipelineStage.S3_VALIDATION_A
    assert agent_b_run.output_snapshot["retry_exhausted"] is True
    assert agent_b_run.output_snapshot["attempt_count"] == 3
    assert "missing_agent_b_feature_coverage" in issue_codes
    assert "missing_agent_b_epic_coverage" in issue_codes
    assert "agent_b_coverage_exhausted" in issue_codes
    assert "agent_b_coverage_exhausted" in risk_codes
    assert repository.list_epics(run_id) == []
    assert repository.list_stories(run_id) == []
    assert repository.list_tasks(run_id) == []
    assert repository.list_sync_events(run_id) == []


def test_agent_b_fails_fast_when_openai_fallback_plan_misses_coverage() -> None:
    gdd_path = _snake_gdd_path()
    if not gdd_path.exists():
        pytest.skip("Root-level Snake Escape GDD is not available.")

    repository = InMemoryWorkflowRepository()
    project_root = Path(__file__).resolve().parents[2]
    agent_client = _OpenAIFallbackPartialAgentBClient(
        project_root / "data" / "snake_escape_fixture.json"
    )
    service = PipelineService(
        repository=repository,
        fixture_path=project_root / "data" / "snake_escape_fixture.json",
        snake_gdd_path=gdd_path,
        agent_client=agent_client,
    )

    triggered = service.trigger_run(
        S0TriggerRequest(project_name="Provider Fallback Game", gdd_file=str(gdd_path))
    )
    run_id = triggered["run_id"]
    service.load_context(run_id, S1ContextRequest())
    service.run_agent_a(run_id)
    _approve_hil1_queue(repository, run_id)

    with pytest.raises(PipelineConflictError) as exc:
        service.run_agent_b(run_id)

    agent_b_run = _agent_b_run(repository, run_id)
    attempt = agent_b_run.output_snapshot["attempts"][0]

    assert exc.value.code == "agent_b_coverage_exhausted"
    assert agent_client.plan_attempts == 1
    assert agent_b_run.output_snapshot["attempt_count"] == 1
    assert attempt["outcome"] == "provider_fallback_incomplete"
    assert attempt["provider"] == "mock_after_openai_network_error"
    assert "static mock planner" in attempt["message"]


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


def test_in_memory_repository_tracks_agent_b_jobs() -> None:
    repository = InMemoryWorkflowRepository()
    jobs = [
        AgentBJob(run_id="run_1", scope_type=AgentBScope.EPIC, scope_id=f"E-{index}")
        for index in range(5)
    ]

    repository.add_agent_b_jobs(jobs)
    updated = jobs[0].model_copy(update={"status": AgentBJobStatus.SUCCESS})
    repository.update_agent_b_job(updated)

    assert len(repository.list_agent_b_jobs("run_1")) == 5
    assert repository.get_agent_b_job(jobs[0].id).status == AgentBJobStatus.SUCCESS


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
    second_questions = repository.list_hil0_questions(second_trigger["run_id"])

    assert first_document.version_id == "v1"
    assert first_document.description_status == GDDDescriptionStatus.USER_PROVIDED
    assert first_questions
    assert second_questions
    assert {question.id for question in first_questions}.isdisjoint(
        {question.id for question in second_questions}
    )
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


def test_hierarchical_agent_b_renumbers_duplicate_task_ids_before_persisting() -> None:
    gdd_path = _snake_gdd_path()
    if not gdd_path.exists():
        pytest.skip("Root-level Snake Escape GDD is not available.")

    repository = InMemoryWorkflowRepository()
    project_root = Path(__file__).resolve().parents[2]
    service = PipelineService(
        repository=repository,
        fixture_path=project_root / "data" / "snake_escape_fixture.json",
        snake_gdd_path=gdd_path,
        agent_client=_DuplicateTaskIdAgentBClient(
            project_root / "data" / "snake_escape_fixture.json"
        ),
    )

    triggered = service.trigger_run(
        S0TriggerRequest(project_name="Duplicate Task ID Game", gdd_file=str(gdd_path))
    )
    run_id = triggered["run_id"]
    service.load_context(run_id, S1ContextRequest())
    service.run_agent_a(run_id)
    _approve_hil1_queue(repository, run_id)
    service.run_agent_b_epics(run_id)
    service.run_agent_b_stories(run_id)
    service.run_agent_b_tasks(run_id)

    tasks = repository.list_tasks(run_id)
    assert len(tasks) == 11
    assert [task.task_id for task in tasks] == [f"T-{index:03d}" for index in range(1, 12)]
    assert len({(task.run_id, task.task_id) for task in tasks}) == len(tasks)


class _RetryingAgentBClient(AgentClient):
    provider = "fake"

    def __init__(self, fixture_path: Path) -> None:
        self.mock = MockAgentClient(fixture_path)
        self.plan_attempts = 0

    def analyze_gdd(
        self,
        run_id: str,
        sections: list[GDDSection],
        *,
        mode: RunMode = RunMode.NEW_GAME,
        delta_report: dict[str, object] | None = None,
        validation_feedback: list[dict[str, object]] | None = None,
        target_section_ids: list[str] | None = None,
    ) -> dict[str, object]:
        return self.mock.analyze_gdd(
            run_id,
            sections,
            mode=mode,
            delta_report=delta_report,
            validation_feedback=validation_feedback,
            target_section_ids=target_section_ids,
        )

    def plan_qa_tasks(
        self,
        run_id: str,
        *,
        hil_context: dict[str, object] | None = None,
    ) -> dict[str, list[object]]:
        self.plan_attempts += 1
        if self.plan_attempts == 1:
            return self.mock.plan_qa_tasks(
                run_id,
                hil_context=_first_feature_context(hil_context),
            )
        return self.mock.plan_qa_tasks(run_id, hil_context=hil_context)

    def generate_test_cases(self, run_id: str, tasks: list[QATask]) -> list[DomainTestCase]:
        return self.mock.generate_test_cases(run_id, tasks)


class _AlwaysPartialAgentBClient(_RetryingAgentBClient):
    def plan_qa_tasks(
        self,
        run_id: str,
        *,
        hil_context: dict[str, object] | None = None,
    ) -> dict[str, list[object]]:
        self.plan_attempts += 1
        return self.mock.plan_qa_tasks(
            run_id,
            hil_context=_first_feature_context(hil_context),
        )


class _OpenAIFallbackPartialAgentBClient(_AlwaysPartialAgentBClient):
    def provider_for(self, operation: str) -> str:
        if operation == "plan_qa_tasks":
            return "mock_after_openai_network_error"
        return self.provider


class _DuplicateTaskIdAgentBClient(MockAgentClient):
    def plan_tasks(
        self,
        run_id: str,
        *,
        story: dict[str, object],
        feature: dict[str, object],
        source_text: dict[str, str],
        task_seq_offset: int,
        past_corrections: list[dict[str, object]] | None = None,
        existing_tasks: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        output = super().plan_tasks(
            run_id,
            story=story,
            feature=feature,
            source_text=source_text,
            task_seq_offset=task_seq_offset,
            past_corrections=past_corrections,
            existing_tasks=existing_tasks,
        )
        return {
            **output,
            "tasks": [
                task.model_copy(update={"task_id": "T-111"})
                for task in output["tasks"]
                if isinstance(task, QATask)
            ],
        }


def _first_feature_context(
    hil_context: dict[str, object] | None,
) -> dict[str, object] | None:
    if hil_context is None:
        return None
    approved_features = hil_context.get("approved_features", [])
    if not isinstance(approved_features, list) or not approved_features:
        return hil_context
    first_feature = next(
        (feature for feature in approved_features if isinstance(feature, dict)),
        None,
    )
    if not first_feature or not isinstance(first_feature.get("feature_id"), str):
        return hil_context
    return {
        **hil_context,
        "approved_feature_ids": [first_feature["feature_id"]],
        "approved_features": [first_feature],
    }


def _approve_hil1_queue(repository: InMemoryWorkflowRepository, run_id: str) -> None:
    for feature in repository.list_features(run_id):
        if feature.review_status in {ReviewStatus.NEEDS_REVIEW, ReviewStatus.BLOCKED}:
            repository.add_review_decision(
                ReviewDecision(
                    run_id=run_id,
                    target_type="feature",
                    target_id=feature.feature_id,
                    decision=ReviewStatus.APPROVED,
                    reviewer="QA Lead",
                )
            )


def _agent_b_run(repository: InMemoryWorkflowRepository, run_id: str) -> AgentRun:
    return next(
        agent_run
        for agent_run in repository.list_agent_runs(run_id)
        if agent_run.stage == PipelineStage.S4_AGENT_B
    )
