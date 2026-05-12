from __future__ import annotations

from collections import Counter
import hashlib
import mimetypes
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from app.domain.models import (
    AgentBJob,
    AgentBJobRetryRequest,
    AgentBJobStatus,
    AgentBScope,
    AgentRun,
    DemoRunRequest,
    Epic,
    EpicMergeRequest,
    EpicPatchRequest,
    EpicSplitRequest,
    Feature,
    GDDDescriptionStatus,
    GDDDocument,
    GDDSection,
    HIL0Action,
    HIL0Question,
    PipelineStage,
    Project,
    ProjectCreateRequest,
    QATask,
    ReviewStatus,
    Run,
    RunMode,
    RunStatus,
    S0TriggerRequest,
    S1ContextRequest,
    StageEvent,
    Story,
    TestCase,
    ValidationIssue,
    ValidationSeverity,
    utc_now,
)
from app.repositories.workflow_repository import WorkflowRepository
from app.services.agent_a_retry import run_agent_a_with_retries
from app.services.agent_b_retry import run_agent_b_with_retries
from app.services.agents import AgentClient
from app.services.agents.mock import MockAgentClient
from app.services.gdd_parser import parse_docx_gdd
from app.services.notion import NotionSyncClient
from app.services.notion.mock import MockNotionSyncClient
from app.services.risk_events import (
    kill_switch_risk_event,
    kill_switch_state,
    risk_events_from_validation_issues,
)
from app.services.review_queues import build_review_queue
from app.services.validators import (
    validate_agent_b1_epic_coverage,
    validate_agent_b2_story_coverage,
    validate_agent_b3_full_plan,
    validate_tasks_with_routing,
    validate_test_cases_with_routing,
)

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class PipelineConflictError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class PipelineService:
    def __init__(
        self,
        repository: WorkflowRepository,
        fixture_path: Path,
        snake_gdd_path: Path,
        upload_dir: Path | None = None,
        max_upload_bytes: int = 10 * 1024 * 1024,
        agent_client: AgentClient | None = None,
        notion_sync_client: NotionSyncClient | None = None,
        agent_b2_parallelism: int = 3,
        agent_b3_parallelism: int = 5,
    ) -> None:
        self.repository = repository
        self.project_root = fixture_path.parents[1]
        self.workspace_root = self.project_root.parent
        self.snake_gdd_path = snake_gdd_path
        self.upload_dir = upload_dir or self.project_root / "backend" / ".runtime" / "uploads"
        self.max_upload_bytes = max_upload_bytes
        self.agent_client = agent_client or MockAgentClient(fixture_path)
        self.notion_sync = notion_sync_client or MockNotionSyncClient()
        self.agent_b2_parallelism = agent_b2_parallelism
        self.agent_b3_parallelism = agent_b3_parallelism

    def create_project(self, request: ProjectCreateRequest) -> Project:
        name = request.name.strip()
        if not name:
            raise ValueError("Project name is required.")

        project_id = request.project_id or self._project_id_from_name(name)
        if request.project_id and self.repository.get_project(project_id) is not None:
            raise ValueError(f"Project already exists: {project_id}")

        project = Project(
            id=project_id,
            name=name,
            source_document=request.source_document or "",
        )
        return self.repository.upsert_project(project)

    def trigger_run(self, request: S0TriggerRequest) -> dict[str, str]:
        if request.project_id:
            project = self.repository.get_project(request.project_id)
            if project is None:
                raise LookupError(f"Project not found: {request.project_id}")
            mode = RunMode.DELTA
        else:
            project = self.create_project(
                ProjectCreateRequest(
                    name=request.project_name or "",
                    source_document=request.gdd_file,
                )
            )
            mode = RunMode.NEW_GAME

        run = self._stage_s0_trigger(project=project, gdd_file=request.gdd_file, mode=mode)
        return {
            "run_id": run.id,
            "project_id": run.project_id,
            "gdd_file": request.gdd_file,
            "mode": run.mode.value,
        }

    def load_context(self, run_id: str, request: S1ContextRequest) -> dict[str, Any]:
        run = self.repository.get_run(run_id)
        if run is None:
            raise LookupError(f"Run not found: {run_id}")

        context = self._stage_s1_context_loader(run, request)
        document = context["gdd_document"]
        sections = context["sections"]
        actionable_sections = [section for section in sections if section.actionable]
        return {
            "run_id": context["run"].id,
            "project_id": context["run"].project_id,
            "mode": context["run"].mode.value,
            "gdd_document": document,
            "section_count": len(sections),
            "actionable_section_count": len(actionable_sections),
            "hil_0_questions": context["hil_0_questions"],
            "delta_report": context["delta_report"],
        }

    def coverage_report(self, run_id: str) -> dict[str, object]:
        if self.repository.get_run(run_id) is None:
            raise LookupError(f"Run not found: {run_id}")
        return self._coverage_report(run_id)

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
        run = self._stage_s0_trigger(project, str(self.snake_gdd_path), request.mode)

        try:
            context = self._stage_s1_context_loader(run, S1ContextRequest())
            run = context["run"]
            sections = context["sections"]

            run = self._stage_s2_agent_a(run, sections, auto_approve=request.auto_approve)
            run = self._stage_s4_agent_b(run, auto_approve=request.auto_approve)
            if run.status == RunStatus.FAILED:
                return run
            run = self._stage_s6_agent_c(run, auto_approve=request.auto_approve)
            return self._stage_finalize(run, auto_approve=request.auto_approve)
        except Exception:
            run.status = RunStatus.FAILED
            run.finished_at = utc_now()
            self.repository.update_run(run)
            raise

    def run_agent_a(self, run_id: str) -> Run:
        run = self._require_run(run_id)
        if not run.session_memory.get("context_loaded"):
            raise PipelineConflictError(
                "gdd_not_loaded",
                "Load S1 context before running Agent A.",
                {"run_id": run_id, "current_stage": run.current_stage.value},
            )
        self._assert_stage(run, PipelineStage.S1_CONTEXT_LOADER)
        sections = self.repository.list_sections(run.id)
        if not sections:
            raise PipelineConflictError(
                "gdd_not_loaded",
                "No parsed GDD sections are available for this run.",
                {"run_id": run.id, "current_stage": run.current_stage.value},
            )
        return self._stage_s2_agent_a(run, sections, auto_approve=False)

    def run_agent_b(self, run_id: str) -> Run:
        run = self._require_run(run_id)
        self._assert_stage(run, PipelineStage.S3_VALIDATION_A)
        self._assert_hil_gate_clear(run.id, "HIL-1")
        return self._stage_s4_agent_b(run, auto_approve=False)

    def run_agent_b_epics(self, run_id: str) -> dict[str, Any]:
        run = self._require_run(run_id)
        if run.current_stage == PipelineStage.S4_1_AGENT_B_EPICS:
            return {"run": run, "epics": self.repository.list_epics(run.id)}
        self._assert_stage(run, PipelineStage.S3_VALIDATION_A)
        self._assert_hil_gate_clear(run.id, "HIL-1")
        run = self._stage_s4_1_epics(run, auto_approve=False)
        return {"run": run, "epics": self.repository.list_epics(run.id)}

    def run_agent_b_stories(self, run_id: str) -> dict[str, Any]:
        run = self._require_run(run_id)
        if run.current_stage == PipelineStage.S4_2_AGENT_B_STORIES:
            return {
                "run": run,
                "stories": self.repository.list_stories(run.id),
                "jobs": self.repository.list_agent_b_jobs(run.id),
            }
        self._assert_stage(run, PipelineStage.S4_1_AGENT_B_EPICS)
        run = self._stage_s4_2_stories(run)
        return {
            "run": run,
            "stories": self.repository.list_stories(run.id),
            "jobs": self.repository.list_agent_b_jobs(run.id),
        }

    def run_agent_b_tasks(self, run_id: str) -> dict[str, Any]:
        run = self._require_run(run_id)
        self._assert_stage(run, PipelineStage.S4_2_AGENT_B_STORIES)
        run = self._stage_s4_3_tasks(run)
        return {
            "run": run,
            "tasks": self.repository.list_tasks(run.id),
            "jobs": self.repository.list_agent_b_jobs(run.id),
        }

    def retry_agent_b_job(
        self,
        run_id: str,
        job_id: str,
        payload: AgentBJobRetryRequest | None = None,
    ) -> AgentBJob:
        _ = payload
        run = self._require_run(run_id)
        job = self.repository.get_agent_b_job(job_id)
        if job is None or job.run_id != run_id:
            raise LookupError(f"Agent B job not found: {job_id}")
        if not job.is_retryable:
            raise PipelineConflictError(
                "agent_b_job_not_retryable",
                "Only failed or timeout Agent B jobs can be retried.",
                {"run_id": run_id, "job_id": job_id, "status": job.status.value},
            )

        features_by_id = {feature.feature_id: feature for feature in self.repository.list_features(run.id)}
        sections = self.repository.list_sections(run.id)
        if job.scope_type == AgentBScope.EPIC:
            epic = self._require_epic(run.id, job.scope_id)
            updated_job, stories, issues, events = self._run_agent_b_story_job(
                run,
                job,
                epic,
                features_by_id,
                sections,
                self._next_story_sequence(run.id),
            )
            if stories:
                existing = [
                    story for story in self.repository.list_stories(run.id)
                    if story.epic_id != epic.epic_id
                ]
                self.repository.set_stories(run.id, [*existing, *stories])
                self.repository.add_validation_issues(issues)
                self._record_risk_events(issues)
                self.repository.add_sync_events(events)
            if self._all_agent_b_jobs_success(run.id, AgentBScope.EPIC):
                self._mark_agent_b_status(run, "s4_2_status", "COMPLETE")
                self._stage(run, PipelineStage.S4_2_AGENT_B_STORIES, "Agent B2 retry completed.")
            return updated_job

        story = self._require_story(run.id, job.scope_id)
        updated_job, tasks = self._run_agent_b_task_job(
            run,
            job,
            story,
            features_by_id,
            sections,
            self._next_task_sequence(run.id, story.feature_id),
        )
        if tasks:
            existing = [
                task for task in self.repository.list_tasks(run.id)
                if task.story_id != story.story_id
            ]
            self.repository.set_tasks(run.id, self._renumber_tasks([*existing, *tasks]))
        if self._all_agent_b_jobs_success(run.id, AgentBScope.STORY):
            self._complete_agent_b_tasks_stage(run)
        return updated_job

    def patch_epic(self, run_id: str, epic_id: str, payload: EpicPatchRequest) -> Epic:
        run = self._require_run(run_id)
        self._assert_epic_edit_open(run)
        epics = self.repository.list_epics(run_id)
        index, epic = self._find_epic(epics, epic_id)
        update = payload.model_dump(exclude_none=True)
        feature_ids = update.get("feature_ids")
        if feature_ids is not None:
            self._validate_epic_feature_ids(run_id, feature_ids)
        updated = epic.model_copy(update={key: value for key, value in update.items() if key != "rationale"})
        epics[index] = updated
        self.repository.set_epics(run_id, epics)
        self._record_epic_edit(run, "patch", {"epic_id": epic_id, "patch": update})
        return updated

    def merge_epics(self, run_id: str, payload: EpicMergeRequest) -> Epic:
        run = self._require_run(run_id)
        self._assert_epic_edit_open(run)
        epics = self.repository.list_epics(run_id)
        source_epics = [self._require_epic(run_id, epic_id) for epic_id in payload.source_epic_ids]
        merged_feature_ids = sorted(
            {feature_id for epic in source_epics for feature_id in epic.feature_ids}
        )
        self._validate_epic_feature_ids(run_id, merged_feature_ids)
        source_ids = {epic.epic_id for epic in source_epics} | {epic.id for epic in source_epics}
        remaining = [
            epic
            for epic in epics
            if epic.epic_id not in source_ids and epic.id not in source_ids
        ]
        merged = Epic(
            id=f"epic_{uuid4().hex[:12]}",
            run_id=run_id,
            epic_id=self._unique_epic_id(remaining, payload.target_title),
            title=payload.target_title,
            description=payload.target_description,
            feature_ids=merged_feature_ids,
            external_id=self._epic_external_id(run.project_id, payload.target_title),
            review_status=ReviewStatus.AUTO_APPROVED,
        )
        self.repository.set_epics(run_id, [*remaining, merged])
        self._record_epic_edit(
            run,
            "merge",
            {
                "source_epic_ids": payload.source_epic_ids,
                "target_epic_id": merged.epic_id,
            },
        )
        return merged

    def split_epic(self, run_id: str, payload: EpicSplitRequest) -> list[Epic]:
        run = self._require_run(run_id)
        self._assert_epic_edit_open(run)
        epics = self.repository.list_epics(run_id)
        _, source_epic = self._find_epic(epics, payload.epic_id)
        requested_feature_ids = [
            feature_id for split in payload.splits for feature_id in split.feature_ids
        ]
        if sorted(requested_feature_ids) != sorted(set(requested_feature_ids)):
            raise PipelineConflictError(
                "epic_edit_feature_coverage",
                "Split feature_ids must not contain duplicates.",
                {"run_id": run_id, "epic_id": payload.epic_id},
            )
        if set(requested_feature_ids) != set(source_epic.feature_ids):
            raise PipelineConflictError(
                "epic_edit_feature_coverage",
                "Split feature_ids must exactly cover the source epic feature_ids.",
                {
                    "run_id": run_id,
                    "epic_id": payload.epic_id,
                    "source_feature_ids": source_epic.feature_ids,
                    "requested_feature_ids": requested_feature_ids,
                },
            )
        remaining = [
            epic
            for epic in epics
            if epic.id != source_epic.id and epic.epic_id != source_epic.epic_id
        ]
        new_epics: list[Epic] = []
        for split in payload.splits:
            new_epics.append(
                Epic(
                    id=f"epic_{uuid4().hex[:12]}",
                    run_id=run_id,
                    epic_id=self._unique_epic_id([*remaining, *new_epics], split.title),
                    title=split.title,
                    description=split.description,
                    feature_ids=split.feature_ids,
                    external_id=self._epic_external_id(run.project_id, split.title),
                    review_status=ReviewStatus.AUTO_APPROVED,
                )
            )
        self.repository.set_epics(run_id, [*remaining, *new_epics])
        self._record_epic_edit(
            run,
            "split",
            {"source_epic_id": payload.epic_id, "new_epic_ids": [epic.epic_id for epic in new_epics]},
        )
        return new_epics

    def run_agent_c(self, run_id: str) -> Run:
        run = self._require_run(run_id)
        self._assert_stage(run, PipelineStage.S5_VALIDATION_B_SYNC)
        self._assert_kill_switch_clear(run)
        self._assert_hil_gate_clear(run.id, "HIL-2")
        return self._stage_s6_agent_c(run, auto_approve=False)

    def finalize_run(self, run_id: str) -> Run:
        run = self._require_run(run_id)
        self._assert_stage(run, PipelineStage.S7_VALIDATION_C_SYNC)
        self._assert_hil_gate_clear(run.id, "HIL-3")
        return self._stage_finalize(run, auto_approve=False)

    def _stage_s2_agent_a(
        self,
        run: Run,
        sections: list[GDDSection],
        *,
        auto_approve: bool,
    ) -> Run:
        agent_a_result = run_agent_a_with_retries(
            agent_client=self.agent_client,
            run_id=run.id,
            sections=sections,
            mode=run.mode,
            delta_report=run.delta_report,
        )
        agent_a_output = agent_a_result.output
        features = agent_a_output["features"]
        self.repository.set_features(run.id, features)
        self.repository.add_agent_run(
            AgentRun(
                run_id=run.id,
                agent_name="Agent A - GDD Analyzer",
                stage=PipelineStage.S2_AGENT_A,
                input_snapshot={"section_count": len(sections)},
                output_snapshot={
                    "feature_count": len(features),
                    "coverage_report": agent_a_output["coverage_report"],
                    "ambiguities": agent_a_output["ambiguities"],
                    "attempt_count": agent_a_result.attempt_count,
                    "retry_exhausted": agent_a_result.exhausted,
                    "attempts": agent_a_result.attempt_log(),
                    "auto_approve": auto_approve,
                },
                provider=self._agent_provider("analyze_gdd"),
            )
        )
        run.session_memory = {
            **run.session_memory,
            "agent_a_validation": {
                "attempt_count": agent_a_result.attempt_count,
                "retry_exhausted": agent_a_result.exhausted,
                "attempts": agent_a_result.attempt_log(),
            },
        }
        run = self.repository.update_run(run)
        run = self._stage(
            run,
            PipelineStage.S2_AGENT_A,
            f"Generated {len(features)} features after {agent_a_result.attempt_count} attempt(s).",
        )

        feature_issues = agent_a_result.issues
        self.repository.set_features(run.id, features)
        self.repository.add_validation_issues(feature_issues)
        self._record_risk_events(feature_issues)
        run = self._stage(
            run,
            PipelineStage.S3_VALIDATION_A,
            f"Feature validation produced {len(feature_issues)} issues.",
        )
        if agent_a_result.exhausted and not features:
            raise ValueError("Agent A failed schema validation after bounded retries.")
        return run

    def _stage_s4_agent_b(self, run: Run, *, auto_approve: bool) -> Run:
        features = self.repository.list_features(run.id)
        sections = self.repository.list_sections(run.id)
        hil1_context = self._build_hil1_context(
            features,
            auto_approve=auto_approve,
        )
        hil1_context = {
            **hil1_context,
            "project_id": run.project_id,
            "mode": run.mode.value,
            "delta_report": run.delta_report or {},
        }
        run.session_memory = {**run.session_memory, "hil_1": hil1_context}
        run = self.repository.update_run(run)

        agent_b_result = run_agent_b_with_retries(
            agent_client=self.agent_client,
            run_id=run.id,
            hil1_context=hil1_context,
        )
        agent_b_output = agent_b_result.output
        epics = agent_b_output["epics"]
        stories = agent_b_output["stories"]
        tasks = agent_b_output["tasks"]
        self.repository.add_agent_run(
            AgentRun(
                run_id=run.id,
                agent_name="Agent B - QA Planner",
                stage=PipelineStage.S4_AGENT_B,
                input_snapshot={
                    "hil_1": self._hil1_agent_input_snapshot(hil1_context),
                },
                output_snapshot={
                    "epic_count": len(epics),
                    "story_count": len(stories),
                    "task_count": len(tasks),
                    "attempt_count": agent_b_result.attempt_count,
                    "retry_exhausted": agent_b_result.exhausted,
                    "attempts": agent_b_result.attempt_log(),
                    "auto_approve": auto_approve,
                },
                provider=self._agent_provider("plan_qa_tasks"),
            )
        )
        run.session_memory = {
            **run.session_memory,
            "agent_b_validation": {
                "attempt_count": agent_b_result.attempt_count,
                "retry_exhausted": agent_b_result.exhausted,
                "attempts": agent_b_result.attempt_log(),
            },
        }
        run = self.repository.update_run(run)
        if agent_b_result.exhausted:
            self.repository.add_validation_issues(agent_b_result.coverage_issues)
            self._record_risk_events(agent_b_result.coverage_issues)
            raise PipelineConflictError(
                "agent_b_coverage_exhausted",
                "Agent B plan is missing approved HIL-1 feature or epic coverage.",
                {
                    "run_id": run.id,
                    "attempt_count": agent_b_result.attempt_count,
                    "issues": [
                        {
                            "code": issue.code,
                            "target_type": issue.target_type,
                            "target_id": issue.target_id,
                            "message": issue.message,
                        }
                        for issue in agent_b_result.coverage_issues
                    ],
                },
            )
        self.repository.set_epics(run.id, epics)
        self.repository.set_stories(run.id, stories)
        tasks = self._renumber_tasks(tasks)
        self.repository.set_tasks(run.id, tasks)
        run = self._stage(
            run,
            PipelineStage.S4_AGENT_B,
            (
                f"Generated {len(epics)} epics, {len(stories)} stories, and "
                f"{len(tasks)} tasks after {agent_b_result.attempt_count} attempt(s)."
            ),
        )

        task_issues = [
            *agent_b_result.coverage_issues,
            *validate_tasks_with_routing(run.id, tasks, features, sections),
        ]
        tasks = self._renumber_tasks(tasks)
        self.repository.set_tasks(run.id, tasks)
        self.repository.add_validation_issues(task_issues)
        self._record_risk_events(task_issues)
        feature_name_by_id = {feature.feature_id: feature.name for feature in features}
        sync_a_events = self._sync_a_epics_stories(epics, stories)
        eligible_tasks = self._eligible_for_sync(tasks)
        sync_b_events = self._sync_b_tasks(eligible_tasks, feature_name_by_id)
        self.repository.add_sync_events(sync_a_events + sync_b_events)
        run = self._stage(
            run,
            PipelineStage.S5_VALIDATION_B_SYNC,
            f"Task validation produced {len(task_issues)} issues; "
            f"Sync-A wrote {len(sync_a_events)} records; "
            f"Sync-B wrote {len(sync_b_events)} task records.",
        )
        run = self._update_kill_switch_state(run)
        if self._should_abort_run(run):
            risk_event = kill_switch_risk_event(
                run.id,
                run.session_memory["kill_switch"],
            )
            self.repository.add_risk_events([risk_event])
            run.status = RunStatus.FAILED
            run.finished_at = utc_now()
            run.coverage_report = self._coverage_report(run.id)
            return self._stage(
                run,
                PipelineStage.S5_VALIDATION_B_SYNC,
                "Kill switch tripped before Agent C.",
            )
        return run

    def _stage_s4_1_epics(self, run: Run, *, auto_approve: bool) -> Run:
        features = self.repository.list_features(run.id)
        hil1_context = self._build_hil1_context(features, auto_approve=auto_approve)
        hil1_context = {
            **hil1_context,
            "project_id": run.project_id,
            "mode": run.mode.value,
            "delta_report": run.delta_report or {},
        }
        run.session_memory = {**run.session_memory, "hil_1": hil1_context}
        run = self.repository.update_run(run)

        output = self.agent_client.plan_epics(run.id, hil_context=hil1_context)
        epics = self._epics_from_output(output)
        issues = validate_agent_b1_epic_coverage(run.id, epics, hil1_context)
        self.repository.add_agent_run(
            AgentRun(
                run_id=run.id,
                agent_name="Agent B1 - Epic Planner",
                stage=PipelineStage.S4_1_AGENT_B_EPICS,
                input_snapshot={"hil_1": self._hil1_agent_input_snapshot(hil1_context)},
                output_snapshot={
                    "epic_count": len(epics),
                    "validation_issue_count": len(issues),
                    "auto_approve": auto_approve,
                },
                provider=self._agent_provider("plan_epics"),
            )
        )
        self.repository.add_validation_issues(issues)
        self._record_risk_events(issues)
        if any(issue.severity == ValidationSeverity.S1_CRITICAL for issue in issues):
            raise PipelineConflictError(
                "agent_b1_coverage_failed",
                "Agent B1 epic coverage failed for approved HIL-1 scope.",
                {
                    "run_id": run.id,
                    "issues": [self._issue_detail(issue) for issue in issues],
                },
            )

        self.repository.set_epics(run.id, epics)
        sync_events = self._sync_a1_epics(epics)
        self.repository.add_sync_events(sync_events)
        return self._stage(
            run,
            PipelineStage.S4_1_AGENT_B_EPICS,
            f"Agent B1 generated {len(epics)} epics; Sync-A1 wrote {len(sync_events)} records.",
        )

    def _stage_s4_2_stories(self, run: Run) -> Run:
        epics = self.repository.list_epics(run.id)
        features_by_id = {feature.feature_id: feature for feature in self.repository.list_features(run.id)}
        sections = self.repository.list_sections(run.id)
        jobs = [
            AgentBJob(run_id=run.id, scope_type=AgentBScope.EPIC, scope_id=epic.epic_id)
            for epic in epics
        ]
        self.repository.add_agent_b_jobs(jobs)

        stories: list[Story] = []
        issues: list[ValidationIssue] = []
        sync_events: list[Any] = []
        story_seq_offset = 1
        for job, epic in zip(jobs, epics, strict=True):
            updated_job, job_stories, job_issues, job_events = self._run_agent_b_story_job(
                run,
                job,
                epic,
                features_by_id,
                sections,
                story_seq_offset,
            )
            story_seq_offset += max(len(job_stories), 1)
            stories.extend(job_stories)
            issues.extend(job_issues)
            sync_events.extend(job_events)
            if updated_job.status != AgentBJobStatus.SUCCESS:
                continue

        self.repository.set_stories(run.id, stories)
        self.repository.add_validation_issues(issues)
        self._record_risk_events(issues)
        self.repository.add_sync_events(sync_events)
        failed_jobs = self._failed_agent_b_jobs(run.id, AgentBScope.EPIC)
        self.repository.add_agent_run(
            AgentRun(
                run_id=run.id,
                agent_name="Agent B2 - Story Planner",
                stage=PipelineStage.S4_2_AGENT_B_STORIES,
                input_snapshot={"epic_count": len(epics), "parallelism": self.agent_b2_parallelism},
                output_snapshot={
                    "story_count": len(stories),
                    "job_count": len(jobs),
                    "failed_job_count": len(failed_jobs),
                    "validation_issue_count": len(issues),
                },
                provider=self._agent_provider("plan_stories"),
            )
        )
        run = self._mark_agent_b_status(
            run,
            "s4_2_status",
            "PARTIAL" if failed_jobs else "COMPLETE",
            failed_jobs=failed_jobs,
        )
        run = self._stage(
            run,
            PipelineStage.S4_2_AGENT_B_STORIES,
            (
                f"Agent B2 generated {len(stories)} stories; "
                f"Sync-A2 wrote {len(sync_events)} records."
            ),
        )
        if failed_jobs:
            raise self._partial_agent_b_failure(run.id, AgentBScope.EPIC, failed_jobs)
        return run

    def _stage_s4_3_tasks(self, run: Run) -> Run:
        stories = self.repository.list_stories(run.id)
        features_by_id = {feature.feature_id: feature for feature in self.repository.list_features(run.id)}
        sections = self.repository.list_sections(run.id)
        jobs = [
            AgentBJob(run_id=run.id, scope_type=AgentBScope.STORY, scope_id=story.story_id)
            for story in stories
        ]
        self.repository.add_agent_b_jobs(jobs)

        tasks: list[QATask] = []
        task_seq_by_feature: dict[str, int] = {}
        for job, story in zip(jobs, stories, strict=True):
            offset = task_seq_by_feature.get(
                story.feature_id,
                self._next_task_sequence(run.id, story.feature_id),
            )
            updated_job, job_tasks = self._run_agent_b_task_job(
                run,
                job,
                story,
                features_by_id,
                sections,
                offset,
            )
            tasks.extend(job_tasks)
            for task in job_tasks:
                task_seq_by_feature[task.feature_id] = (
                    max(task_seq_by_feature.get(task.feature_id, offset), offset)
                    + 1
                )
            if updated_job.status != AgentBJobStatus.SUCCESS:
                continue

        tasks = self._renumber_tasks(tasks)
        self.repository.set_tasks(run.id, tasks)
        failed_jobs = self._failed_agent_b_jobs(run.id, AgentBScope.STORY)
        self.repository.add_agent_run(
            AgentRun(
                run_id=run.id,
                agent_name="Agent B3 - Task Planner",
                stage=PipelineStage.S4_3_AGENT_B_TASKS,
                input_snapshot={"story_count": len(stories), "parallelism": self.agent_b3_parallelism},
                output_snapshot={
                    "task_count": len(tasks),
                    "job_count": len(jobs),
                    "failed_job_count": len(failed_jobs),
                },
                provider=self._agent_provider("plan_tasks"),
            )
        )
        run = self._mark_agent_b_status(
            run,
            "s4_3_status",
            "PARTIAL" if failed_jobs else "COMPLETE",
            failed_jobs=failed_jobs,
        )
        run = self._stage(
            run,
            PipelineStage.S4_3_AGENT_B_TASKS,
            f"Agent B3 generated {len(tasks)} tasks across {len(jobs)} story jobs.",
        )
        if failed_jobs:
            raise self._partial_agent_b_failure(run.id, AgentBScope.STORY, failed_jobs)
        return self._complete_agent_b_tasks_stage(run)

    def _complete_agent_b_tasks_stage(self, run: Run) -> Run:
        features = self.repository.list_features(run.id)
        sections = self.repository.list_sections(run.id)
        epics = self.repository.list_epics(run.id)
        stories = self.repository.list_stories(run.id)
        tasks = self.repository.list_tasks(run.id)
        task_issues = validate_agent_b3_full_plan(
            run.id,
            epics=epics,
            stories=stories,
            tasks=tasks,
            features=features,
            sections=sections,
        )
        self.repository.set_tasks(run.id, tasks)
        self.repository.add_validation_issues(task_issues)
        self._record_risk_events(task_issues)
        feature_name_by_id = {feature.feature_id: feature.name for feature in features}
        eligible_tasks = self._eligible_for_sync(tasks)
        sync_b_events = self._sync_b_tasks(eligible_tasks, feature_name_by_id)
        self.repository.add_sync_events(sync_b_events)
        run = self._stage(
            run,
            PipelineStage.S5_VALIDATION_B_SYNC,
            f"Agent B3 validation produced {len(task_issues)} issues; "
            f"Sync-B wrote {len(sync_b_events)} task records.",
        )
        run = self._update_kill_switch_state(run)
        if self._should_abort_run(run):
            risk_event = kill_switch_risk_event(run.id, run.session_memory["kill_switch"])
            self.repository.add_risk_events([risk_event])
            run.status = RunStatus.FAILED
            run.finished_at = utc_now()
            run.coverage_report = self._coverage_report(run.id)
            return self._stage(
                run,
                PipelineStage.S5_VALIDATION_B_SYNC,
                "Kill switch tripped before Agent C.",
            )
        return run

    def _stage_s6_agent_c(self, run: Run, *, auto_approve: bool) -> Run:
        tasks = self.repository.list_tasks(run.id)
        features = self.repository.list_features(run.id)
        sections = self.repository.list_sections(run.id)
        test_cases = self._generate_test_cases(run, tasks, features, sections)
        self.repository.set_test_cases(run.id, test_cases)
        self.repository.add_agent_run(
            AgentRun(
                run_id=run.id,
                agent_name="Agent C - Test Case Generator",
                stage=PipelineStage.S6_AGENT_C,
                input_snapshot={"task_count": len(tasks)},
                output_snapshot={
                    "test_case_count": len(test_cases),
                    "auto_approve": auto_approve,
                },
                provider=self._agent_provider("generate_test_cases"),
            )
        )
        run = self._stage(
            run,
            PipelineStage.S6_AGENT_C,
            f"Generated {len(test_cases)} test cases.",
        )

        test_case_issues = validate_test_cases_with_routing(
            run.id,
            test_cases,
            tasks,
            sections,
        )
        self.repository.set_test_cases(run.id, test_cases)
        self.repository.add_validation_issues(test_case_issues)
        self._record_risk_events(test_case_issues)
        eligible_test_cases = self._eligible_for_sync(test_cases)
        test_case_sync_events = self._sync_c_test_cases(eligible_test_cases, tasks)
        self.repository.add_sync_events(test_case_sync_events)
        return self._stage(
            run,
            PipelineStage.S7_VALIDATION_C_SYNC,
            (
                f"Test-case validation produced {len(test_case_issues)} issues; "
                f"synced {len(test_case_sync_events)} mock Notion records."
            ),
        )

    def _generate_test_cases(
        self,
        run: Run,
        tasks: list[QATask],
        features: list[Feature],
        sections: list[GDDSection],
    ) -> list[TestCase]:
        try:
            return self.agent_client.generate_test_cases(
                run.id,
                tasks,
                features=features,
                sections=sections,
            )
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc):
                raise
            return self.agent_client.generate_test_cases(run.id, tasks)

    def _stage_finalize(self, run: Run, *, auto_approve: bool) -> Run:
        coverage_report = self._coverage_report(run.id)
        run.coverage_report = coverage_report
        run.status = RunStatus.COMPLETED
        run.finished_at = utc_now()
        return self._stage(run, PipelineStage.FINAL_COVERAGE, "Coverage report is ready.")

    def _require_run(self, run_id: str) -> Run:
        run = self.repository.get_run(run_id)
        if run is None:
            raise LookupError(f"Run not found: {run_id}")
        return run

    def _assert_stage(self, run: Run, expected_stage: PipelineStage) -> None:
        if run.current_stage == expected_stage:
            return
        raise PipelineConflictError(
            "wrong_stage",
            f"Run is at {run.current_stage.value}; expected {expected_stage.value}.",
            {
                "run_id": run.id,
                "current_stage": run.current_stage.value,
                "expected_stage": expected_stage.value,
                "status": run.status.value,
            },
        )

    def _assert_hil_gate_clear(self, run_id: str, tier: str) -> None:
        queue = build_review_queue(self.repository, run_id, tier)
        if queue.item_count == 0:
            return
        raise PipelineConflictError(
            "hil_gate_blocked",
            f"{queue.hil_tier} has {queue.item_count} item(s) still awaiting review.",
            {
                "run_id": run_id,
                "tier": queue.hil_tier,
                "pending_count": queue.item_count,
                "groups": [
                    {
                        "group_id": group.group_id,
                        "reviewer": group.reviewer,
                        "feature_id": group.feature_id,
                        "epic_id": group.epic_id,
                        "item_count": group.item_count,
                    }
                    for group in queue.groups
                ],
            },
        )

    def _assert_kill_switch_clear(self, run: Run) -> None:
        if run.status == RunStatus.FAILED or self._should_abort_run(run):
            raise PipelineConflictError(
                "kill_switch_tripped",
                "Run is halted by the kill switch.",
                {
                    "run_id": run.id,
                    "current_stage": run.current_stage.value,
                    "kill_switch": run.session_memory.get("kill_switch", {}),
                },
            )

    def _stage_s0_trigger(self, project: Project, gdd_file: str, mode: RunMode) -> Run:
        run = self.repository.create_run(
            Run(
                project_id=project.id,
                mode=mode,
                session_memory={
                    "project_id": project.id,
                    "gdd_file": gdd_file,
                    "mode": mode.value,
                    "context_loaded": False,
                },
            )
        )
        return self._stage(
            run,
            PipelineStage.S0_TRIGGER,
            f"Triggered {mode.value} run for project '{project.name}'.",
        )

    def _stage_s1_context_loader(
        self,
        run: Run,
        request: S1ContextRequest,
    ) -> dict[str, Any]:
        gdd_file = run.session_memory.get("gdd_file")
        if not isinstance(gdd_file, str) or not gdd_file.strip():
            raise ValueError("Run session memory does not include a GDD file reference.")

        gdd_path = self._resolve_gdd_file(gdd_file)
        raw_bytes = gdd_path.read_bytes()
        if len(raw_bytes) > self.max_upload_bytes:
            raise ValueError(
                f"GDD file is {len(raw_bytes)} bytes, exceeding limit {self.max_upload_bytes}."
            )

        previous_document = self.repository.get_latest_gdd_document(run.project_id)
        document = GDDDocument(
            project_id=run.project_id,
            run_id=run.id,
            version_id=self.repository.next_gdd_version_id(run.project_id),
            description=request.description,
            description_status=(
                GDDDescriptionStatus.USER_PROVIDED
                if request.description
                else GDDDescriptionStatus.PENDING
            ),
            parent_document_id=(
                previous_document.id
                if run.mode == RunMode.DELTA and previous_document is not None
                else None
            ),
            file_name=gdd_path.name,
            file_path=str(gdd_path),
            content_type=request.content_type or self._content_type_for(gdd_path),
            origin=request.origin,
            size_bytes=len(raw_bytes),
            sha256=hashlib.sha256(raw_bytes).hexdigest(),
        )
        self.repository.create_gdd_document(document)

        parsed = parse_docx_gdd(gdd_path, run.id)
        self.repository.add_sections(parsed.sections)
        hil_0_questions = self._build_hil0_questions(run.id, parsed.sections)
        self.repository.add_hil0_questions(hil_0_questions)
        delta_report = self._build_delta_report(run, document, parsed.sections, previous_document)

        run.gdd_document_id = document.id
        run.source_version_id = document.version_id
        run.source_metadata = {
            "file_name": document.file_name,
            "content_type": document.content_type,
            "origin": document.origin,
            "size_bytes": document.size_bytes,
            "sha256": document.sha256,
        }
        run.delta_report = delta_report
        run.session_memory = {
            **run.session_memory,
            "context_loaded": True,
            "gdd_document_id": document.id,
            "source_version_id": document.version_id,
            "actionable_section_count": len(
                [section for section in parsed.sections if section.actionable]
            ),
            "hil_0_question_count": len(hil_0_questions),
        }

        run = self._stage(
            run,
            PipelineStage.S1_CONTEXT_LOADER,
            f"Registered {document.version_id} and parsed {len(parsed.sections)} GDD sections.",
        )
        return {
            "run": run,
            "gdd_document": document,
            "sections": parsed.sections,
            "hil_0_questions": hil_0_questions,
            "delta_report": delta_report,
        }

    def _stage(self, run: Run, stage: PipelineStage, message: str) -> Run:
        run.current_stage = stage
        if run.status != RunStatus.FAILED:
            run.status = RunStatus.RUNNING if stage != PipelineStage.FINAL_COVERAGE else run.status
        run.timeline.append(StageEvent(stage=stage, status="ok", message=message))
        return self.repository.update_run(run)

    def _coverage_report(self, run_id: str) -> dict[str, object]:
        run = self.repository.get_run(run_id)
        sections = self.repository.list_sections(run_id)
        features = self.repository.list_features(run_id)
        tasks = self.repository.list_tasks(run_id)
        test_cases = self.repository.list_test_cases(run_id)
        issues = self.repository.list_validation_issues(run_id)
        risk_events = self.repository.list_risk_events(run_id)
        sync_events = self.repository.list_sync_events(run_id)

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
            "risk_summary": self._risk_summary(risk_events),
            "sync_summary": self._sync_summary(sync_events),
            "gdd_version_metadata": {
                "gdd_document_id": run.gdd_document_id if run else None,
                "source_version_id": run.source_version_id if run else None,
                "source_metadata": run.source_metadata if run else {},
            },
            "sign_off": {
                "signed_off": bool(run and run.signed_off_at),
                "signed_off_by": run.signed_off_by if run else None,
                "signed_off_at": run.signed_off_at.isoformat()
                if run and run.signed_off_at
                else None,
            },
        }

    def _run_agent_b_story_job(
        self,
        run: Run,
        job: AgentBJob,
        epic: Epic,
        features_by_id: dict[str, Feature],
        sections: list[GDDSection],
        story_seq_offset: int,
    ) -> tuple[AgentBJob, list[Story], list[ValidationIssue], list[Any]]:
        started = utc_now()
        job = job.model_copy(
            update={
                "status": AgentBJobStatus.RUNNING,
                "attempt_count": job.attempt_count + 1,
                "started_at": job.started_at or started,
                "finished_at": None,
                "error_code": None,
                "error_message": None,
            }
        )
        self.repository.update_agent_b_job(job)
        try:
            epic_features = [
                features_by_id[feature_id]
                for feature_id in epic.feature_ids
                if feature_id in features_by_id
            ]
            output = self.agent_client.plan_stories(
                run.id,
                epic={
                    **epic.model_dump(mode="json"),
                    "project_id": run.project_id,
                    "mode": run.mode.value,
                },
                features=[self._hil1_feature_snapshot(feature) for feature in epic_features],
                source_text=self._source_text_for_features(epic_features, sections),
                story_seq_offset=story_seq_offset,
            )
            stories = self._stories_from_output(output)
            issues = validate_agent_b2_story_coverage(run.id, epic, stories, epic_features)
            events = self._sync_a2_stories(epic, stories)
            job = job.model_copy(
                update={
                    "status": AgentBJobStatus.SUCCESS,
                    "finished_at": utc_now(),
                    "output_summary": {
                        "story_count": len(stories),
                        "validation_issue_codes": sorted({issue.code for issue in issues}),
                    },
                }
            )
            return self.repository.update_agent_b_job(job), stories, issues, events
        except Exception as exc:
            failed = self._failed_job(job, exc)
            return self.repository.update_agent_b_job(failed), [], [], []

    def _run_agent_b_task_job(
        self,
        run: Run,
        job: AgentBJob,
        story: Story,
        features_by_id: dict[str, Feature],
        sections: list[GDDSection],
        task_seq_offset: int,
    ) -> tuple[AgentBJob, list[QATask]]:
        started = utc_now()
        job = job.model_copy(
            update={
                "status": AgentBJobStatus.RUNNING,
                "attempt_count": job.attempt_count + 1,
                "started_at": job.started_at or started,
                "finished_at": None,
                "error_code": None,
                "error_message": None,
            }
        )
        self.repository.update_agent_b_job(job)
        try:
            feature = features_by_id.get(story.feature_id)
            if feature is None:
                raise ValueError(f"Feature not found for story {story.story_id}: {story.feature_id}")
            output = self.agent_client.plan_tasks(
                run.id,
                story={
                    **story.model_dump(mode="json"),
                    "project_id": run.project_id,
                    "mode": run.mode.value,
                },
                feature=self._hil1_feature_snapshot(feature),
                source_text=self._source_text_for_features([feature], sections),
                task_seq_offset=task_seq_offset,
            )
            tasks = self._tasks_from_output(output)
            job = job.model_copy(
                update={
                    "status": AgentBJobStatus.SUCCESS,
                    "finished_at": utc_now(),
                    "output_summary": {"task_count": len(tasks)},
                }
            )
            return self.repository.update_agent_b_job(job), tasks
        except Exception as exc:
            failed = self._failed_job(job, exc)
            return self.repository.update_agent_b_job(failed), []

    def _failed_job(self, job: AgentBJob, exc: Exception) -> AgentBJob:
        exc_name = type(exc).__name__
        status = (
            AgentBJobStatus.TIMEOUT
            if "timeout" in exc_name.lower() or "timeout" in str(exc).lower()
            else AgentBJobStatus.FAILED
        )
        return job.model_copy(
            update={
                "status": status,
                "finished_at": utc_now(),
                "error_code": exc_name,
                "error_message": str(exc)[:500],
            }
        )

    def _epics_from_output(self, output: dict[str, Any]) -> list[Epic]:
        epics = output.get("epics")
        if not isinstance(epics, list) or not all(isinstance(epic, Epic) for epic in epics):
            raise ValueError("Agent B1 output must include a list of Epic models.")
        return epics

    def _stories_from_output(self, output: dict[str, Any]) -> list[Story]:
        stories = output.get("stories")
        if not isinstance(stories, list) or not all(isinstance(story, Story) for story in stories):
            raise ValueError("Agent B2 output must include a list of Story models.")
        return stories

    def _tasks_from_output(self, output: dict[str, Any]) -> list[QATask]:
        tasks = output.get("tasks")
        if not isinstance(tasks, list) or not all(isinstance(task, QATask) for task in tasks):
            raise ValueError("Agent B3 output must include a list of QATask models.")
        return tasks

    def _source_text_for_features(
        self,
        features: list[Feature],
        sections: list[GDDSection],
    ) -> dict[str, str]:
        wanted = {
            section_id
            for feature in features
            for section_id in feature.source_sections
        }
        return {
            section.section_id: section.text
            for section in sections
            if section.section_id in wanted and section.text
        }

    def _sync_a1_epics(self, epics: list[Epic]) -> list[Any]:
        return self.notion_sync.upsert_epics_batch(epics)

    def _sync_a2_stories(self, epic: Epic, stories: list[Story]) -> list[Any]:
        return self.notion_sync.upsert_stories_for_epic(epic, stories)

    def _failed_agent_b_jobs(self, run_id: str, scope: AgentBScope) -> list[AgentBJob]:
        return [
            job
            for job in self.repository.list_agent_b_jobs(run_id)
            if job.scope_type == scope and job.status in {AgentBJobStatus.FAILED, AgentBJobStatus.TIMEOUT}
        ]

    def _all_agent_b_jobs_success(self, run_id: str, scope: AgentBScope) -> bool:
        jobs = [
            job
            for job in self.repository.list_agent_b_jobs(run_id)
            if job.scope_type == scope
        ]
        return bool(jobs) and all(job.status == AgentBJobStatus.SUCCESS for job in jobs)

    def _partial_agent_b_failure(
        self,
        run_id: str,
        scope: AgentBScope,
        failed_jobs: list[AgentBJob],
    ) -> PipelineConflictError:
        return PipelineConflictError(
            "agent_b_substage_partial_failure",
            (
                f"Agent B {scope.value} fan-out completed with {len(failed_jobs)} "
                "failed job(s). Retry failed jobs and re-run the substage."
            ),
            {
                "run_id": run_id,
                "scope_type": scope.value,
                "failed_jobs": [self._job_detail(job) for job in failed_jobs],
            },
        )

    def _job_detail(self, job: AgentBJob) -> dict[str, Any]:
        return {
            "job_id": job.id,
            "scope_type": job.scope_type.value,
            "scope_id": job.scope_id,
            "status": job.status.value,
            "attempt_count": job.attempt_count,
            "error_code": job.error_code,
            "error_message": job.error_message,
        }

    def _issue_detail(self, issue: ValidationIssue) -> dict[str, Any]:
        return {
            "code": issue.code,
            "target_type": issue.target_type,
            "target_id": issue.target_id,
            "message": issue.message,
        }

    def _mark_agent_b_status(
        self,
        run: Run,
        key: str,
        status: str,
        *,
        failed_jobs: list[AgentBJob] | None = None,
    ) -> Run:
        run.session_memory = {
            **run.session_memory,
            key: {
                "status": status,
                "failed_jobs": [self._job_detail(job) for job in failed_jobs or []],
            },
        }
        return self.repository.update_run(run)

    def _next_story_sequence(self, run_id: str) -> int:
        stories = self.repository.list_stories(run_id)
        return len(stories) + 1

    def _next_task_sequence(self, run_id: str, feature_id: str) -> int:
        existing = [
            task for task in self.repository.list_tasks(run_id)
            if task.feature_id == feature_id
        ]
        return len(existing) + 1

    def _renumber_tasks(self, tasks: list[QATask]) -> list[QATask]:
        return [
            task.model_copy(update={"task_id": f"T-{index:03d}"})
            for index, task in enumerate(tasks, start=1)
        ]

    def _require_epic(self, run_id: str, epic_id: str) -> Epic:
        return self._find_epic(self.repository.list_epics(run_id), epic_id)[1]

    def _require_story(self, run_id: str, story_id: str) -> Story:
        for story in self.repository.list_stories(run_id):
            if story.id == story_id or story.story_id == story_id:
                return story
        raise LookupError(f"Story not found: {story_id}")

    def _find_epic(self, epics: list[Epic], epic_id: str) -> tuple[int, Epic]:
        for index, epic in enumerate(epics):
            if epic.id == epic_id or epic.epic_id == epic_id:
                return index, epic
        raise LookupError(f"Epic not found: {epic_id}")

    def _assert_epic_edit_open(self, run: Run) -> None:
        if run.current_stage == PipelineStage.S4_1_AGENT_B_EPICS:
            return
        raise PipelineConflictError(
            "epic_edit_after_lock",
            "Epics can only be edited between S4.1 and S4.2.",
            {"run_id": run.id, "current_stage": run.current_stage.value},
        )

    def _validate_epic_feature_ids(self, run_id: str, feature_ids: list[str]) -> None:
        known_feature_ids = {feature.feature_id for feature in self.repository.list_features(run_id)}
        unknown = sorted(set(feature_ids) - known_feature_ids)
        if unknown:
            raise PipelineConflictError(
                "epic_edit_unknown_feature",
                "Epic edit references feature_ids that do not exist on this run.",
                {"run_id": run_id, "feature_ids": unknown},
            )

    def _record_epic_edit(self, run: Run, action: str, payload: dict[str, Any]) -> None:
        edit_log = list(run.session_memory.get("epic_edit_log", []))
        edit_log.append({"action": action, "payload": payload, "created_at": utc_now().isoformat()})
        run.session_memory = {**run.session_memory, "epic_edit_log": edit_log}
        self.repository.update_run(run)

    def _unique_epic_id(self, existing: list[Epic], title: str) -> str:
        base = f"E-{_safe_id(title).upper().replace('_', '-')}"
        candidate = base
        suffix = 2
        existing_ids = {epic.epic_id for epic in existing}
        while candidate in existing_ids:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def _epic_external_id(self, project_id: str, title: str) -> str:
        return f"{project_id}-{self._unique_external_suffix(title)}"

    def _unique_external_suffix(self, title: str) -> str:
        return f"E-{_safe_id(title).upper().replace('_', '-')}"

    def _sync_a_epics_stories(self, epics: list[Any], stories: list[Any]) -> list[Any]:
        events = [self.notion_sync.upsert_epic(epic) for epic in epics]
        events.extend(self.notion_sync.upsert_story(story) for story in stories)
        return events

    def _sync_b_tasks(
        self,
        tasks: list[Any],
        feature_name_by_id: dict[str, str],
    ) -> list[Any]:
        return [
            self.notion_sync.upsert_task(task, feature_name_by_id.get(task.feature_id, "Unknown"))
            for task in tasks
        ]

    def _sync_c_test_cases(self, test_cases: list[Any], tasks: list[Any]) -> list[Any]:
        events = [self.notion_sync.upsert_test_case(test_case) for test_case in test_cases]
        synced_task_ids = {test_case.related_task_id for test_case in test_cases}
        for task in tasks:
            if task.task_id in synced_task_ids and task.review_status in {
                ReviewStatus.AUTO_APPROVED,
                ReviewStatus.APPROVED,
            }:
                task.status = "Test Cases Ready"
        if tasks:
            self.repository.set_tasks(tasks[0].run_id, tasks)
        return events

    def _eligible_for_sync(self, items: list[Any]) -> list[Any]:
        return [
            item
            for item in items
            if item.review_status in {ReviewStatus.AUTO_APPROVED, ReviewStatus.APPROVED}
        ]

    def _record_risk_events(self, issues: list[Any]) -> None:
        self.repository.add_risk_events(risk_events_from_validation_issues(issues))

    def _update_kill_switch_state(self, run: Run) -> Run:
        state = kill_switch_state(self.repository.list_risk_events(run.id))
        run.session_memory = {**run.session_memory, "kill_switch": state}
        return self.repository.update_run(run)

    def _should_abort_run(self, run: Run) -> bool:
        kill_switch = run.session_memory.get("kill_switch", {})
        return bool(isinstance(kill_switch, dict) and kill_switch.get("tripped"))

    def _agent_provider(self, operation: str) -> str:
        return self.agent_client.provider_for(operation)

    def _build_hil1_context(
        self,
        features: list[Any],
        *,
        auto_approve: bool,
    ) -> dict[str, object]:
        approved_statuses = {ReviewStatus.AUTO_APPROVED, ReviewStatus.APPROVED}
        excluded_statuses = {ReviewStatus.BLOCKED, ReviewStatus.REJECTED}
        queue_statuses = {ReviewStatus.NEEDS_REVIEW, ReviewStatus.BLOCKED}
        approved_features = [
            feature
            for feature in features
            if (
                feature.review_status not in excluded_statuses
                if auto_approve
                else feature.review_status in approved_statuses
            )
        ]
        approved_feature_ids = [feature.feature_id for feature in approved_features]
        review_queue_feature_ids = [
            feature.feature_id for feature in features if feature.review_status in queue_statuses
        ]
        held_feature_ids = [
            feature.feature_id
            for feature in features
            if feature.feature_id not in set(approved_feature_ids)
        ]
        return {
            "source": "HIL-1",
            "approval_mode": "demo_auto_approve" if auto_approve else "router_status",
            "approved_feature_ids": approved_feature_ids,
            "held_feature_ids": held_feature_ids,
            "review_queue_feature_ids": review_queue_feature_ids,
            "approved_features": [
                self._hil1_feature_snapshot(feature) for feature in approved_features
            ],
            "epic_structure": self._hil1_epic_structure(approved_features),
        }

    def _hil1_feature_snapshot(self, feature: Any) -> dict[str, object]:
        return {
            "feature_id": feature.feature_id,
            "name": feature.name,
            "summary": feature.summary,
            "feature_type": feature.feature_type.value,
            "source_sections": feature.source_sections,
            "key_behaviors": feature.key_behaviors,
            "dependencies": feature.dependencies,
            "confidence": feature.confidence,
            "assignee": feature.assignee,
            "review_status": feature.review_status.value,
            "lane": feature.lane,
            "delta_status": feature.delta_status.value if feature.delta_status else None,
        }

    def _hil1_epic_structure(self, features: list[Any]) -> dict[str, object]:
        grouped: dict[str, list[Any]] = {}
        for feature in features:
            grouped.setdefault(feature.feature_type.value, []).append(feature)
        return {
            "source": "feature_type_grouping",
            "epics": [
                {
                    "epic_id": f"HIL1-{_safe_id(feature_type).upper().replace('_', '-')}",
                    "title": f"{feature_type.replace('_', ' ').title()} Scope",
                    "feature_ids": [feature.feature_id for feature in group],
                }
                for feature_type, group in grouped.items()
            ],
        }

    def _hil1_agent_input_snapshot(self, hil1_context: dict[str, object]) -> dict[str, object]:
        epic_structure = hil1_context.get("epic_structure", {})
        epic_candidates = (
            epic_structure.get("epics", [])
            if isinstance(epic_structure, dict)
            else []
        )
        return {
            "approved_feature_ids": hil1_context["approved_feature_ids"],
            "held_feature_ids": hil1_context["held_feature_ids"],
            "review_queue_feature_ids": hil1_context["review_queue_feature_ids"],
            "epic_candidate_count": len(epic_candidates),
        }

    def _risk_summary(self, risk_events: list[Any]) -> dict[str, object]:
        return {
            "total": len(risk_events),
            "by_severity": dict(sorted(Counter(event.severity.value for event in risk_events).items())),
            "by_code": dict(sorted(Counter(event.code for event in risk_events).items())),
        }

    def _sync_summary(self, sync_events: list[Any]) -> dict[str, object]:
        return {
            "total": len(sync_events),
            "by_status": dict(sorted(Counter(event.status.value for event in sync_events).items())),
            "by_phase": dict(
                sorted(
                    Counter(event.payload.get("sync_phase", "unknown") for event in sync_events).items()
                )
            ),
        }

    def _project_id_from_name(self, name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "project"
        candidate = base
        suffix = 2
        while self.repository.get_project(candidate) is not None:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def _resolve_gdd_file(self, gdd_file: str) -> Path:
        raw_path = Path(gdd_file)
        candidates = (
            [raw_path]
            if raw_path.is_absolute()
            else [
                self.upload_dir / raw_path,
                self.project_root / raw_path,
                self.workspace_root / raw_path,
                Path.cwd() / raw_path,
            ]
        )
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        raise FileNotFoundError(f"GDD file not found: {gdd_file}")

    def _content_type_for(self, path: Path) -> str:
        return mimetypes.guess_type(path.name)[0] or DOCX_CONTENT_TYPE

    def _build_hil0_questions(self, run_id: str, sections: list[GDDSection]) -> list[HIL0Question]:
        questions: list[HIL0Question] = []
        run_key = _safe_id(run_id)
        for section in sections:
            for flag in section.flags:
                questions.append(
                    HIL0Question(
                        id=f"hil0_{run_key}_{_safe_id(section.section_id)}_{len(questions) + 1}",
                        run_id=run_id,
                        section_id=section.section_id,
                        title=section.title,
                        reason="flagged_note",
                        question=flag,
                        allowed_actions=[
                            HIL0Action.PROVIDE_ARTIFACT,
                            HIL0Action.PROCEED_WITH_FLAG,
                            HIL0Action.SKIP_SECTION,
                        ],
                    )
                )
            if section.actionability_reason == "insufficient_text":
                questions.append(
                    HIL0Question(
                        id=f"hil0_{run_key}_{_safe_id(section.section_id)}_{len(questions) + 1}",
                        run_id=run_id,
                        section_id=section.section_id,
                        title=section.title,
                        reason="thin_section",
                        question="Section has limited detail. Proceed with a confidence flag?",
                        allowed_actions=[
                            HIL0Action.PROVIDE_ARTIFACT,
                            HIL0Action.PROCEED_WITH_FLAG,
                            HIL0Action.SKIP_SECTION,
                        ],
                    )
                )
            if section.actionability_reason == "external_dependency":
                questions.append(
                    HIL0Question(
                        id=f"hil0_{run_key}_{_safe_id(section.section_id)}_{len(questions) + 1}",
                        run_id=run_id,
                        section_id=section.section_id,
                        title=section.title,
                        reason="external_dependency",
                        question=(
                            "Section references an external document and was excluded from AI analysis. "
                            "Confirm coverage is handled externally, or provide the artifact."
                        ),
                        allowed_actions=[
                            HIL0Action.PROVIDE_ARTIFACT,
                            HIL0Action.PROCEED_WITH_FLAG,
                            HIL0Action.SKIP_SECTION,
                        ],
                    )
                )
        return questions

    def _build_delta_report(
        self,
        run: Run,
        document: GDDDocument,
        sections: list[GDDSection],
        previous_document: GDDDocument | None,
    ) -> dict[str, Any] | None:
        if run.mode != RunMode.DELTA:
            return None

        previous_sections = (
            self.repository.list_sections(previous_document.run_id)
            if previous_document is not None and previous_document.run_id is not None
            else []
        )
        previous_by_id = {
            section.section_id: _section_fingerprint(section) for section in previous_sections
        }
        current_by_id = {section.section_id: _section_fingerprint(section) for section in sections}

        new_sections = sorted(set(current_by_id) - set(previous_by_id))
        removed_sections = sorted(set(previous_by_id) - set(current_by_id))
        shared_sections = sorted(set(current_by_id) & set(previous_by_id))
        modified_sections = [
            section_id
            for section_id in shared_sections
            if current_by_id[section_id] != previous_by_id[section_id]
        ]
        unchanged_sections = [
            section_id
            for section_id in shared_sections
            if current_by_id[section_id] == previous_by_id[section_id]
        ]

        return {
            "status": "READY" if previous_document is not None else "NO_BASELINE",
            "current_document_id": document.id,
            "current_version_id": document.version_id,
            "previous_document_id": previous_document.id if previous_document else None,
            "previous_version_id": previous_document.version_id if previous_document else None,
            "buckets": {
                "NEW": new_sections,
                "MODIFIED": modified_sections,
                "UNCHANGED": unchanged_sections,
                "REMOVED": removed_sections,
            },
            "summary": {
                "new": len(new_sections),
                "modified": len(modified_sections),
                "unchanged": len(unchanged_sections),
                "removed": len(removed_sections),
            },
        }


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower() or "section"


def _section_fingerprint(section: GDDSection) -> str:
    payload = f"{section.title}\n{section.text}\n{section.tables}\n{section.flags}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
