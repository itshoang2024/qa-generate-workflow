from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import (
    DeltaStatus,
    Epic,
    Estimate,
    Feature,
    FeatureType,
    GDDSection,
    Priority,
    QATask,
    ReviewStatus,
    RunMode,
    Story,
    TaskDeltaStatus,
)
from app.domain.qa_roster import QA_ASSIGNEE_BY_FEATURE_TYPE, QA_MEMBERS

AmbiguityAction = Literal["ask_user", "skip", "proceed_with_flag"]

AGENT_A_NAME_MAX_LENGTH = 80
AGENT_A_SUMMARY_MAX_LENGTH = 300
AGENT_A_FEATURE_ID_PATTERN = r"^F-[0-9]{3}$"
AGENT_B_STORY_ID_PATTERN = r"^S-[0-9]{3,}$"
AGENT_B_TASK_ID_PATTERN = r"^T-[0-9]{3,}$"
AGENT_B_TASK_TITLE_MAX_LENGTH = 100


class AgentAFeatureOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_id: str = Field(pattern=AGENT_A_FEATURE_ID_PATTERN)
    name: str = Field(max_length=AGENT_A_NAME_MAX_LENGTH)
    summary: str = Field(max_length=AGENT_A_SUMMARY_MAX_LENGTH)
    feature_type: FeatureType
    source_sections: list[str] = Field(min_length=1)
    key_behaviors: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    delta_status: DeltaStatus | None = None


class AgentACoverageReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_input_sections: int = Field(ge=0)
    covered_sections: list[str] = Field(default_factory=list)
    uncovered_sections: list[str] = Field(default_factory=list)


class AgentAAmbiguity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    issue: str
    suggested_action: AmbiguityAction = "ask_user"


class AgentAOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    features: list[AgentAFeatureOutput]
    coverage_report: AgentACoverageReport
    ambiguities: list[AgentAAmbiguity] = Field(default_factory=list)

    def to_domain_features(
        self,
        run_id: str,
        feature_ambiguities: dict[str, list[str]] | None = None,
    ) -> list[Feature]:
        ambiguities_by_feature = feature_ambiguities or {}
        features: list[Feature] = []
        for item in self.features:
            is_cross_cutting = item.feature_type == FeatureType.CROSS_CUTTING
            features.append(
                Feature(
                    id=f"feat_{uuid4().hex[:12]}",
                    run_id=run_id,
                    feature_id=item.feature_id,
                    name=item.name,
                    summary=item.summary,
                    feature_type=item.feature_type,
                    source_sections=item.source_sections,
                    key_behaviors=item.key_behaviors,
                    dependencies=item.dependencies,
                    assignee=QA_ASSIGNEE_BY_FEATURE_TYPE[item.feature_type],
                    confidence=item.confidence,
                    delta_status=item.delta_status,
                    cross_cutting_flag=is_cross_cutting,
                    ambiguities=ambiguities_by_feature.get(item.feature_id, []),
                    review_status=(
                        ReviewStatus.BLOCKED
                        if is_cross_cutting
                        else ReviewStatus.AUTO_APPROVED
                        if item.confidence >= 0.85
                        else ReviewStatus.NEEDS_REVIEW
                    ),
                )
            )
        return features


class AgentBTaskOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(pattern=AGENT_B_TASK_ID_PATTERN)
    feature_id: str
    title: str = Field(max_length=AGENT_B_TASK_TITLE_MAX_LENGTH)
    description: str
    assignee: str
    priority: Priority
    priority_justification: str = Field(min_length=1)
    estimate: Estimate
    source_sections: list[str] = Field(min_length=1)
    external_id: str = Field(min_length=1)
    delta_status: TaskDeltaStatus | None = None
    confidence: float = Field(ge=0, le=1)


class AgentBStoryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_id: str = Field(pattern=AGENT_B_STORY_ID_PATTERN)
    title: str
    description: str
    feature_id: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    external_id: str = Field(min_length=1)
    tasks: list[AgentBTaskOutput] = Field(min_length=1)


class AgentBEpicOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    epic_id: str
    title: str
    description: str
    feature_ids: list[str] = Field(min_length=1)
    external_id: str = Field(min_length=1)
    stories: list[AgentBStoryOutput] = Field(min_length=1)


class AgentBOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    epics: list[AgentBEpicOutput]

    def to_domain_plan(
        self,
        run_id: str,
        *,
        feature_context_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, list[Epic | Story | QATask]]:
        epics: list[Epic] = []
        stories: list[Story] = []
        tasks: list[QATask] = []
        allowed_feature_ids = set(feature_context_by_id)

        for epic_item in self.epics:
            filtered_feature_ids = [
                feature_id
                for feature_id in epic_item.feature_ids
                if not allowed_feature_ids or feature_id in allowed_feature_ids
            ]
            epic_stories: list[AgentBStoryOutput] = [
                story
                for story in epic_item.stories
                if not allowed_feature_ids or story.feature_id in allowed_feature_ids
            ]
            if not filtered_feature_ids:
                filtered_feature_ids = sorted({story.feature_id for story in epic_stories})
            if not epic_stories or not filtered_feature_ids:
                continue

            epics.append(
                Epic(
                    id=f"epic_{uuid4().hex[:12]}",
                    run_id=run_id,
                    epic_id=epic_item.epic_id,
                    title=epic_item.title,
                    description=epic_item.description,
                    feature_ids=filtered_feature_ids,
                    external_id=epic_item.external_id,
                    review_status=ReviewStatus.AUTO_APPROVED,
                )
            )
            for story_item in epic_stories:
                feature_context = feature_context_by_id.get(story_item.feature_id, {})
                stories.append(
                    Story(
                        id=f"story_{uuid4().hex[:12]}",
                        run_id=run_id,
                        story_id=story_item.story_id,
                        epic_id=epic_item.epic_id,
                        title=story_item.title,
                        description=story_item.description,
                        feature_id=story_item.feature_id,
                        acceptance_criteria=story_item.acceptance_criteria,
                        external_id=story_item.external_id,
                        review_status=ReviewStatus.AUTO_APPROVED,
                    )
                )
                for task_item in story_item.tasks:
                    if allowed_feature_ids and task_item.feature_id not in allowed_feature_ids:
                        continue
                    task_feature_context = feature_context_by_id.get(
                        task_item.feature_id,
                        feature_context,
                    )
                    assignee = _assignee_for_feature(task_feature_context, task_item.assignee)
                    tasks.append(
                        QATask(
                            id=f"task_{uuid4().hex[:12]}",
                            run_id=run_id,
                            task_id=task_item.task_id,
                            story_id=story_item.story_id,
                            epic_id=epic_item.epic_id,
                            feature_id=task_item.feature_id,
                            title=task_item.title,
                            description=task_item.description,
                            assignee=assignee,
                            priority=task_item.priority,
                            priority_justification=task_item.priority_justification,
                            estimate=task_item.estimate,
                            source_sections=task_item.source_sections,
                            external_id=task_item.external_id,
                            delta_status=task_item.delta_status,
                            confidence=task_item.confidence,
                            status=_task_status_for_delta(task_item.delta_status),
                            review_status=(
                                ReviewStatus.NEEDS_REVIEW
                                if task_item.delta_status == TaskDeltaStatus.ARCHIVE
                                else ReviewStatus.AUTO_APPROVED
                                if task_item.confidence >= 0.85
                                else ReviewStatus.NEEDS_REVIEW
                            ),
                        )
                    )

        return {"epics": epics, "stories": stories, "tasks": tasks}


AGENT_A_SYSTEM_PROMPT = """You are GDD-Analyzer, an AI agent that converts game design document
sections into a structured feature inventory for QA planning.

Hard rules:
1. Return only JSON that matches the supplied schema.
2. Every feature must cite at least one input section_id in source_sections.
3. Never invent section_ids or feature behavior that is not supported by the cited sections.
4. Missing or vague information belongs in ambiguities, not in invented features.
5. If one feature spans 3 or more sections and 2 or more feature types, classify it as cross_cutting.
6. In DELTA mode, set delta_status for every feature. In NEW_GAME mode, set delta_status to null.
7. Keep each feature name at or under 80 characters and each summary at or under 300 characters.
8. Feature IDs must be sequential and zero-padded as F-001, F-002, F-003, ...
"""


AGENT_A_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "features": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "feature_id": {
                        "type": "string",
                        "pattern": AGENT_A_FEATURE_ID_PATTERN,
                    },
                    "name": {
                        "type": "string",
                        "maxLength": AGENT_A_NAME_MAX_LENGTH,
                    },
                    "summary": {
                        "type": "string",
                        "maxLength": AGENT_A_SUMMARY_MAX_LENGTH,
                    },
                    "feature_type": {
                        "type": "string",
                        "enum": [feature_type.value for feature_type in FeatureType],
                    },
                    "source_sections": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                    "key_behaviors": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                    "delta_status": {
                        "type": ["string", "null"],
                        "enum": [status.value for status in DeltaStatus] + [None],
                    },
                },
                "required": [
                    "feature_id",
                    "name",
                    "summary",
                    "feature_type",
                    "source_sections",
                    "key_behaviors",
                    "dependencies",
                    "confidence",
                    "delta_status",
                ],
                "additionalProperties": False,
            },
        },
        "coverage_report": {
            "type": "object",
            "properties": {
                "total_input_sections": {"type": "integer"},
                "covered_sections": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "uncovered_sections": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["total_input_sections", "covered_sections", "uncovered_sections"],
            "additionalProperties": False,
        },
        "ambiguities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section_id": {"type": "string"},
                    "issue": {"type": "string"},
                    "suggested_action": {
                        "type": "string",
                        "enum": ["ask_user", "skip", "proceed_with_flag"],
                    },
                },
                "required": ["section_id", "issue", "suggested_action"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["features", "coverage_report", "ambiguities"],
    "additionalProperties": False,
}


AGENT_B_SYSTEM_PROMPT = """You are QA-Planner, an AI agent that breaks approved
game features into an Epic -> Story -> Task QA execution plan.

Hard rules:
1. Return only JSON that matches the supplied schema.
2. Every task must reference a valid input feature_id.
3. Every task must cite source_sections from its feature.
4. The assignee field must be copied from kb_rules.assignee_mapping by feature_type.
   Do not invent or rebalance assignees.
5. priority_justification is required and must cite the relevant source or risk.
6. Do not invent behavior that is not supported by approved feature summaries.
7. In DELTA mode, skip UNCHANGED features. For MODIFIED features, create
   update/retest tasks and reuse existing external_id values when behavior matches.
   For NEW features, create normal tasks. For REMOVED features, create archive
   confirmation tasks.
8. Task titles must be action-oriented and at most 100 characters.
"""


AGENT_B_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "epics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "epic_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "feature_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                    "external_id": {"type": "string", "minLength": 1},
                    "stories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "story_id": {
                                    "type": "string",
                                    "pattern": AGENT_B_STORY_ID_PATTERN,
                                },
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "feature_id": {"type": "string"},
                                "acceptance_criteria": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "external_id": {"type": "string", "minLength": 1},
                                "tasks": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "task_id": {
                                                "type": "string",
                                                "pattern": AGENT_B_TASK_ID_PATTERN,
                                            },
                                            "feature_id": {"type": "string"},
                                            "title": {
                                                "type": "string",
                                                "maxLength": AGENT_B_TASK_TITLE_MAX_LENGTH,
                                            },
                                            "description": {"type": "string"},
                                            "assignee": {
                                                "type": "string",
                                                "enum": sorted(QA_MEMBERS),
                                            },
                                            "priority": {
                                                "type": "string",
                                                "enum": [priority.value for priority in Priority],
                                            },
                                            "priority_justification": {
                                                "type": "string",
                                                "minLength": 1,
                                            },
                                            "estimate": {
                                                "type": "string",
                                                "enum": [estimate.value for estimate in Estimate],
                                            },
                                            "source_sections": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                                "minItems": 1,
                                            },
                                            "external_id": {"type": "string", "minLength": 1},
                                            "delta_status": {
                                                "type": ["string", "null"],
                                                "enum": [
                                                    status.value for status in TaskDeltaStatus
                                                ]
                                                + [None],
                                            },
                                            "confidence": {
                                                "type": "number",
                                                "minimum": 0,
                                                "maximum": 1,
                                            },
                                        },
                                        "required": [
                                            "task_id",
                                            "feature_id",
                                            "title",
                                            "description",
                                            "assignee",
                                            "priority",
                                            "priority_justification",
                                            "estimate",
                                            "source_sections",
                                            "external_id",
                                            "delta_status",
                                            "confidence",
                                        ],
                                        "additionalProperties": False,
                                    },
                                    "minItems": 1,
                                },
                            },
                            "required": [
                                "story_id",
                                "title",
                                "description",
                                "feature_id",
                                "acceptance_criteria",
                                "external_id",
                                "tasks",
                            ],
                            "additionalProperties": False,
                        },
                        "minItems": 1,
                    },
                },
                "required": [
                    "epic_id",
                    "title",
                    "description",
                    "feature_ids",
                    "external_id",
                    "stories",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["epics"],
    "additionalProperties": False,
}


def build_agent_a_input(
    *,
    mode: RunMode,
    sections: list[GDDSection],
    delta_report: dict[str, Any] | None = None,
    validation_feedback: list[dict[str, Any]] | None = None,
    target_section_ids: list[str] | None = None,
) -> dict[str, Any]:
    target_section_set = set(target_section_ids or [])
    payload: dict[str, Any] = {
        "mode": mode.value,
        "actionable_sections": [
            {
                "section_id": section.section_id,
                "title": section.title,
                "text": section.text,
                "tables": section.tables,
                "parent_section_id": section.parent_id,
            }
            for section in sections
            if section.actionable
            and (not target_section_set or section.section_id in target_section_set)
        ],
        "user_clarifications": [],
    }
    if mode == RunMode.DELTA:
        payload["delta_report"] = delta_report or {}
    if validation_feedback:
        payload["validation_feedback"] = validation_feedback
    if target_section_ids:
        payload["target_section_ids"] = target_section_ids
    return payload


def build_agent_b_input(hil_context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = hil_context or {}
    epic_structure = context.get("epic_structure", {})
    epic_grouping = (
        epic_structure.get("epics", [])
        if isinstance(epic_structure, dict)
        else []
    )
    payload: dict[str, Any] = {
        "project_id": context.get("project_id", "project"),
        "mode": context.get("mode", RunMode.NEW_GAME.value),
        "features": list(agent_b_feature_context_by_id(context).values()),
        "epic_grouping": epic_grouping,
        "kb_rules": {
            "assignee_mapping": {
                feature_type.value: assignee
                for feature_type, assignee in QA_ASSIGNEE_BY_FEATURE_TYPE.items()
            },
            "task_count_warn": {"min_per_story": 1, "max_per_story": 8},
        },
    }
    if context.get("mode") == RunMode.DELTA.value:
        payload["delta_report"] = context.get("delta_report") or {}
        payload["existing_tasks"] = context.get("existing_tasks") or []
    return payload


def agent_b_feature_context_by_id(
    hil_context: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    context = hil_context or {}
    raw_features = context.get("approved_features", [])
    if not isinstance(raw_features, list):
        return {}

    feature_context: dict[str, dict[str, Any]] = {}
    for raw_feature in raw_features:
        if not isinstance(raw_feature, dict):
            continue
        feature_id = raw_feature.get("feature_id")
        if not isinstance(feature_id, str) or not feature_id:
            continue
        feature_context[feature_id] = {
            "feature_id": feature_id,
            "name": raw_feature.get("name", ""),
            "summary": raw_feature.get("summary", ""),
            "feature_type": raw_feature.get("feature_type"),
            "source_sections": raw_feature.get("source_sections", []),
            "key_behaviors": raw_feature.get("key_behaviors", []),
            "dependencies": raw_feature.get("dependencies", []),
            "confidence": raw_feature.get("confidence", 1.0),
            "assignee": raw_feature.get("assignee"),
            "review_status": raw_feature.get("review_status"),
            "delta_status": raw_feature.get("delta_status"),
        }
    return feature_context


def serialize_agent_a_output(output: AgentAOutput) -> dict[str, Any]:
    return output.model_dump(mode="json")


def serialize_agent_b_output(output: AgentBOutput) -> dict[str, Any]:
    return output.model_dump(mode="json")


def _assignee_for_feature(feature_context: dict[str, Any], fallback: str) -> str:
    feature_type = _feature_type_from_context(feature_context)
    if feature_type is None:
        return fallback
    return QA_ASSIGNEE_BY_FEATURE_TYPE[feature_type]


def _feature_type_from_context(feature_context: dict[str, Any]) -> FeatureType | None:
    raw_feature_type = feature_context.get("feature_type")
    if isinstance(raw_feature_type, FeatureType):
        return raw_feature_type
    if isinstance(raw_feature_type, str):
        try:
            return FeatureType(raw_feature_type)
        except ValueError:
            return None
    return None


def _task_status_for_delta(delta_status: TaskDeltaStatus | None) -> str:
    if delta_status == TaskDeltaStatus.UPDATE_RETEST:
        return "Needs Retest"
    if delta_status == TaskDeltaStatus.ARCHIVE:
        return "Archive Pending Lead Review"
    return "Ready for Test Cases"
