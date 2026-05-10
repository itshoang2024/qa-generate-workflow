from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.domain.models import (
    AgentRun,
    DemoRunRequest,
    PipelineStage,
    Project,
    Run,
    RunStatus,
    StageEvent,
    utc_now,
)
from app.repositories.workflow_repository import WorkflowRepository
from app.services.gdd_parser import parse_docx_gdd
from app.services.mock_agents import MockAgentClient
from app.services.notion_sync import MockNotionSyncClient
from app.services.validators import validate_features, validate_tasks, validate_test_cases


class PipelineService:
    def __init__(
        self,
        repository: WorkflowRepository,
        fixture_path: Path,
        snake_gdd_path: Path,
    ) -> None:
        self.repository = repository
        self.snake_gdd_path = snake_gdd_path
        self.agent_client = MockAgentClient(fixture_path)
        self.notion_sync = MockNotionSyncClient()

    def run_demo(self, request: DemoRunRequest) -> Run:
        if request.preset != "snake_escape":
            raise ValueError("Only the 'snake_escape' preset is supported in Phase 1.")

        project = self.repository.upsert_project(
            Project(
                id="snake-escape",
                name="Snake Escape",
                source_document=str(self.snake_gdd_path),
            )
        )
        run = self.repository.create_run(Run(project_id=project.id, mode=request.mode))

        try:
            run = self._stage(run, PipelineStage.S0_TRIGGER, "Started Snake Escape demo run.")
            parsed = parse_docx_gdd(self.snake_gdd_path, run.id)
            self.repository.add_sections(parsed.sections)
            run = self._stage(
                run,
                PipelineStage.S1_CONTEXT_LOADER,
                f"Parsed {len(parsed.sections)} GDD sections from the Snake Escape sample.",
            )

            agent_a_output = self.agent_client.analyze_gdd(run.id, parsed.sections)
            features = agent_a_output["features"]
            self.repository.set_features(run.id, features)
            self.repository.add_agent_run(
                AgentRun(
                    run_id=run.id,
                    agent_name="Agent A - GDD Analyzer",
                    stage=PipelineStage.S2_AGENT_A,
                    input_snapshot={"section_count": len(parsed.sections)},
                    output_snapshot={
                        "feature_count": len(features),
                        "ambiguities": agent_a_output["ambiguities"],
                    },
                )
            )
            run = self._stage(run, PipelineStage.S2_AGENT_A, f"Generated {len(features)} features.")

            feature_issues = validate_features(run.id, features, parsed.sections)
            self.repository.add_validation_issues(feature_issues)
            run = self._stage(
                run,
                PipelineStage.S3_VALIDATION_A,
                f"Feature validation produced {len(feature_issues)} issues.",
            )

            agent_b_output = self.agent_client.plan_qa_tasks(run.id)
            epics = agent_b_output["epics"]
            stories = agent_b_output["stories"]
            tasks = agent_b_output["tasks"]
            self.repository.set_epics(run.id, epics)
            self.repository.set_stories(run.id, stories)
            self.repository.set_tasks(run.id, tasks)
            self.repository.add_agent_run(
                AgentRun(
                    run_id=run.id,
                    agent_name="Agent B - QA Planner",
                    stage=PipelineStage.S4_AGENT_B,
                    input_snapshot={"feature_count": len(features)},
                    output_snapshot={
                        "epic_count": len(epics),
                        "story_count": len(stories),
                        "task_count": len(tasks),
                    },
                )
            )
            run = self._stage(
                run,
                PipelineStage.S4_AGENT_B,
                f"Generated {len(epics)} epics, {len(stories)} stories, and {len(tasks)} tasks.",
            )

            task_issues = validate_tasks(run.id, tasks, features, parsed.sections)
            self.repository.add_validation_issues(task_issues)
            feature_name_by_id = {feature.feature_id: feature.name for feature in features}
            sync_events = []
            sync_events.extend(self.notion_sync.upsert_epic(epic) for epic in epics)
            sync_events.extend(self.notion_sync.upsert_story(story) for story in stories)
            sync_events.extend(
                self.notion_sync.upsert_task(task, feature_name_by_id.get(task.feature_id, "Unknown"))
                for task in tasks
            )
            self.repository.add_sync_events(sync_events)
            run = self._stage(
                run,
                PipelineStage.S5_VALIDATION_B_SYNC,
                f"Task validation produced {len(task_issues)} issues; synced {len(sync_events)} mock Notion records.",
            )

            test_cases = self.agent_client.generate_test_cases(run.id, tasks)
            self.repository.set_test_cases(run.id, test_cases)
            self.repository.add_agent_run(
                AgentRun(
                    run_id=run.id,
                    agent_name="Agent C - Test Case Generator",
                    stage=PipelineStage.S6_AGENT_C,
                    input_snapshot={"task_count": len(tasks)},
                    output_snapshot={"test_case_count": len(test_cases)},
                )
            )
            run = self._stage(
                run,
                PipelineStage.S6_AGENT_C,
                f"Generated {len(test_cases)} test cases.",
            )

            test_case_issues = validate_test_cases(run.id, test_cases, tasks, parsed.sections)
            self.repository.add_validation_issues(test_case_issues)
            test_case_sync_events = [
                self.notion_sync.upsert_test_case(test_case) for test_case in test_cases
            ]
            self.repository.add_sync_events(test_case_sync_events)
            run = self._stage(
                run,
                PipelineStage.S7_VALIDATION_C_SYNC,
                (
                    f"Test-case validation produced {len(test_case_issues)} issues; "
                    f"synced {len(test_case_sync_events)} mock Notion records."
                ),
            )

            coverage_report = self._coverage_report(run.id)
            run.coverage_report = coverage_report
            run.status = RunStatus.COMPLETED
            run.finished_at = utc_now()
            run = self._stage(run, PipelineStage.FINAL_COVERAGE, "Coverage report is ready.")
            return run
        except Exception:
            run.status = RunStatus.FAILED
            run.finished_at = utc_now()
            self.repository.update_run(run)
            raise

    def _stage(self, run: Run, stage: PipelineStage, message: str) -> Run:
        run.current_stage = stage
        run.status = RunStatus.RUNNING if stage != PipelineStage.FINAL_COVERAGE else run.status
        run.timeline.append(StageEvent(stage=stage, status="ok", message=message))
        return self.repository.update_run(run)

    def _coverage_report(self, run_id: str) -> dict[str, object]:
        sections = self.repository.list_sections(run_id)
        features = self.repository.list_features(run_id)
        tasks = self.repository.list_tasks(run_id)
        test_cases = self.repository.list_test_cases(run_id)
        issues = self.repository.list_validation_issues(run_id)

        actionable_sections = [section.section_id for section in sections if section.actionable]
        covered_sections = sorted({source for feature in features for source in feature.source_sections})
        uncovered_sections = sorted(set(actionable_sections) - set(covered_sections))
        assignees = Counter(task.assignee for task in tasks)
        priorities = Counter(task.priority.value for task in tasks)

        return {
            "total_sections": len(sections),
            "actionable_sections": len(actionable_sections),
            "covered_sections": covered_sections,
            "uncovered_sections": uncovered_sections,
            "feature_count": len(features),
            "task_count": len(tasks),
            "test_case_count": len(test_cases),
            "validation_issue_count": len(issues),
            "tasks_by_assignee": dict(sorted(assignees.items())),
            "tasks_by_priority": dict(sorted(priorities.items())),
        }

