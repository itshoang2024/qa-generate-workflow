from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RunMode(StrEnum):
    NEW_GAME = "NEW_GAME"
    DELTA = "DELTA"


class RunStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PipelineStage(StrEnum):
    S0_TRIGGER = "S0_TRIGGER"
    S1_CONTEXT_LOADER = "S1_CONTEXT_LOADER"
    S2_AGENT_A = "S2_AGENT_A"
    S3_VALIDATION_A = "S3_VALIDATION_A"
    S4_AGENT_B = "S4_AGENT_B"
    S5_VALIDATION_B_SYNC = "S5_VALIDATION_B_SYNC"
    S6_AGENT_C = "S6_AGENT_C"
    S7_VALIDATION_C_SYNC = "S7_VALIDATION_C_SYNC"
    FINAL_COVERAGE = "FINAL_COVERAGE"


class FeatureType(StrEnum):
    GAMEPLAY_LOGIC = "gameplay_logic"
    UI_LAYOUT = "ui_layout"
    LEVEL_PUZZLE = "level_puzzle"
    ECONOMY = "economy"
    BACKEND_LIVEOPS = "backend_liveops"
    ANIMATION = "animation"
    TUTORIAL = "tutorial"


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class Estimate(StrEnum):
    S = "S"
    M = "M"
    L = "L"


class ReviewStatus(StrEnum):
    PENDING = "PENDING"
    AUTO_APPROVED = "AUTO_APPROVED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"


class ValidationSeverity(StrEnum):
    S1_CRITICAL = "S1_CRITICAL"
    S2_RECOVERABLE = "S2_RECOVERABLE"
    S3_INFORMATIONAL = "S3_INFORMATIONAL"


class SyncStatus(StrEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REPLAYED = "REPLAYED"


class GDDDescriptionStatus(StrEnum):
    PENDING = "PENDING"
    USER_PROVIDED = "USER_PROVIDED"
    AI_GENERATED = "AI_GENERATED"


class HIL0Action(StrEnum):
    PROVIDE_ARTIFACT = "provide_artifact"
    PROCEED_WITH_FLAG = "proceed_with_flag"
    SKIP_SECTION = "skip_section"


class TestCategory(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    EDGE = "edge"
    INTEGRATION = "integration"


class TestType(StrEnum):
    FUNCTIONAL = "functional"
    UI = "ui"
    INTEGRATION = "integration"
    REGRESSION = "regression"
    PERFORMANCE = "performance"


class Project(BaseModel):
    id: str = Field(default_factory=lambda: f"project_{uuid4().hex[:12]}")
    name: str
    source_document: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class GDDDocument(BaseModel):
    id: str = Field(default_factory=lambda: f"gdd_{uuid4().hex[:12]}")
    project_id: str
    run_id: str | None = None
    version_id: str
    description: str | None = None
    description_status: GDDDescriptionStatus = GDDDescriptionStatus.PENDING
    parent_document_id: str | None = None
    file_name: str
    file_path: str
    content_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    origin: str = "local_reference"
    size_bytes: int
    sha256: str
    created_at: datetime = Field(default_factory=utc_now)


class StageEvent(BaseModel):
    stage: PipelineStage
    status: str
    message: str
    created_at: datetime = Field(default_factory=utc_now)


class Run(BaseModel):
    id: str = Field(default_factory=lambda: f"run_{uuid4().hex[:12]}")
    project_id: str
    mode: RunMode
    status: RunStatus = RunStatus.CREATED
    current_stage: PipelineStage = PipelineStage.S0_TRIGGER
    session_memory: dict[str, Any] = Field(default_factory=dict)
    gdd_document_id: str | None = None
    source_version_id: str | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    delta_report: dict[str, Any] | None = None
    coverage_report: dict[str, Any] = Field(default_factory=dict)
    timeline: list[StageEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None


class GDDSection(BaseModel):
    id: str
    run_id: str
    section_id: str
    title: str
    level: int
    parent_id: str | None = None
    text: str = ""
    tables: list[list[list[str]]] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    actionable: bool = True
    actionability_reason: str | None = None


class HIL0Question(BaseModel):
    id: str = Field(default_factory=lambda: f"hil0_{uuid4().hex[:12]}")
    run_id: str
    section_id: str
    title: str
    reason: str
    question: str
    allowed_actions: list[HIL0Action] = Field(
        default_factory=lambda: [
            HIL0Action.PROVIDE_ARTIFACT,
            HIL0Action.PROCEED_WITH_FLAG,
            HIL0Action.SKIP_SECTION,
        ]
    )
    status: str = "OPEN"
    resolved_action: HIL0Action | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Feature(BaseModel):
    id: str
    run_id: str
    feature_id: str
    name: str
    summary: str
    feature_type: FeatureType
    source_sections: list[str]
    key_behaviors: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    assignee: str
    confidence: float = Field(ge=0, le=1)
    ambiguities: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.PENDING


class Epic(BaseModel):
    id: str
    run_id: str
    epic_id: str
    title: str
    description: str
    feature_ids: list[str]
    external_id: str
    review_status: ReviewStatus = ReviewStatus.PENDING


class Story(BaseModel):
    id: str
    run_id: str
    story_id: str
    epic_id: str
    title: str
    description: str
    feature_id: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    external_id: str
    review_status: ReviewStatus = ReviewStatus.PENDING


class QATask(BaseModel):
    id: str
    run_id: str
    task_id: str
    story_id: str
    epic_id: str
    feature_id: str
    title: str
    description: str
    assignee: str
    priority: Priority
    estimate: Estimate
    source_sections: list[str]
    external_id: str
    confidence: float = Field(ge=0, le=1)
    status: str = "Ready for Test Cases"
    review_status: ReviewStatus = ReviewStatus.PENDING


class TestCase(BaseModel):
    id: str
    run_id: str
    test_case_id: str
    title: str
    type: TestType
    category: TestCategory
    priority: Priority
    preconditions: list[str]
    steps: list[str]
    expected_result: str
    related_task_id: str
    source_sections: list[str]
    external_id: str
    test_data: dict[str, Any] = Field(default_factory=dict)
    status: str = "Not Run"
    review_status: ReviewStatus = ReviewStatus.PENDING


class ValidationIssue(BaseModel):
    id: str = Field(default_factory=lambda: f"vi_{uuid4().hex[:12]}")
    run_id: str
    target_type: str
    target_id: str
    severity: ValidationSeverity
    code: str
    message: str
    stage: PipelineStage
    created_at: datetime = Field(default_factory=utc_now)


class ReviewDecision(BaseModel):
    id: str = Field(default_factory=lambda: f"rd_{uuid4().hex[:12]}")
    run_id: str
    target_type: str
    target_id: str
    decision: ReviewStatus
    reviewer: str = "demo_user"
    comment: str | None = None
    patch: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=utc_now)


class HIL0Resolution(BaseModel):
    id: str = Field(default_factory=lambda: f"hil0r_{uuid4().hex[:12]}")
    run_id: str
    question_id: str
    action: HIL0Action
    reviewer: str = "demo_user"
    response: str | None = None
    artifact_ref: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class AgentRun(BaseModel):
    id: str = Field(default_factory=lambda: f"agent_{uuid4().hex[:12]}")
    run_id: str
    agent_name: str
    stage: PipelineStage
    input_snapshot: dict[str, Any]
    output_snapshot: dict[str, Any]
    provider: str = "mock"
    created_at: datetime = Field(default_factory=utc_now)


class SyncEvent(BaseModel):
    id: str = Field(default_factory=lambda: f"sync_{uuid4().hex[:12]}")
    run_id: str
    target_type: str
    target_id: str
    external_id: str
    action: str
    provider: str = "mock_notion"
    status: SyncStatus = SyncStatus.SUCCESS
    payload: dict[str, Any]
    retry_count: int = 0
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DemoRunRequest(BaseModel):
    preset: str = "snake_escape"
    mode: RunMode = RunMode.NEW_GAME
    auto_approve: bool = True


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1)
    project_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("project_id", "id"),
    )
    source_document: str | None = None


class S0TriggerRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_id: str | None = None
    project_name: str | None = None
    gdd_file: str = Field(validation_alias=AliasChoices("gdd_file", "gdd_file_ref"))

    @model_validator(mode="after")
    def validate_project_selection(self) -> "S0TriggerRequest":
        if bool(self.project_id) == bool(self.project_name):
            raise ValueError("Provide exactly one of project_id or project_name.")
        return self


class S1ContextRequest(BaseModel):
    description: str | None = None
    content_type: str | None = None
    origin: str = "local_reference"


class HIL0ResolutionRequest(BaseModel):
    question_id: str
    action: HIL0Action
    reviewer: str = "demo_user"
    response: str | None = None
    artifact_ref: str | None = None


class ReviewDecisionRequest(BaseModel):
    run_id: str
    target_type: str
    target_id: str
    decision: ReviewStatus
    reviewer: str = "demo_user"
    comment: str | None = None
    patch: dict[str, Any] | None = None
