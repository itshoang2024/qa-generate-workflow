from __future__ import annotations

from collections import Counter
import hashlib
import mimetypes
from pathlib import Path
import re
from typing import Any

from app.domain.models import (
    AgentRun,
    DemoRunRequest,
    GDDDescriptionStatus,
    GDDDocument,
    GDDSection,
    HIL0Action,
    HIL0Question,
    PipelineStage,
    Project,
    ProjectCreateRequest,
    Run,
    RunMode,
    RunStatus,
    S0TriggerRequest,
    S1ContextRequest,
    StageEvent,
    utc_now,
)
from app.repositories.workflow_repository import WorkflowRepository
from app.services.gdd_parser import parse_docx_gdd
from app.services.mock_agents import MockAgentClient
from app.services.notion_sync import MockNotionSyncClient
from app.services.validators import validate_features, validate_tasks, validate_test_cases

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class PipelineService:
    def __init__(
        self,
        repository: WorkflowRepository,
        fixture_path: Path,
        snake_gdd_path: Path,
        upload_dir: Path | None = None,
        max_upload_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self.repository = repository
        self.project_root = fixture_path.parents[1]
        self.workspace_root = self.project_root.parent
        self.snake_gdd_path = snake_gdd_path
        self.upload_dir = upload_dir or self.project_root / "backend" / ".runtime" / "uploads"
        self.max_upload_bytes = max_upload_bytes
        self.agent_client = MockAgentClient(fixture_path)
        self.notion_sync = MockNotionSyncClient()

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

            agent_a_output = self.agent_client.analyze_gdd(run.id, sections)
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
                        "ambiguities": agent_a_output["ambiguities"],
                    },
                )
            )
            run = self._stage(run, PipelineStage.S2_AGENT_A, f"Generated {len(features)} features.")

            feature_issues = validate_features(run.id, features, sections)
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

            task_issues = validate_tasks(run.id, tasks, features, sections)
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
                f"Task validation produced {len(task_issues)} issues; "
                f"synced {len(sync_events)} mock Notion records.",
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

            test_case_issues = validate_test_cases(run.id, test_cases, tasks, sections)
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
        for section in sections:
            for flag in section.flags:
                questions.append(
                    HIL0Question(
                        id=f"hil0_{_safe_id(section.section_id)}_{len(questions) + 1}",
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
                        id=f"hil0_{_safe_id(section.section_id)}_{len(questions) + 1}",
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
