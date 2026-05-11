from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import (
    DeltaStatus,
    Feature,
    FeatureType,
    GDDSection,
    ReviewStatus,
    RunMode,
)
from app.domain.qa_roster import QA_ASSIGNEE_BY_FEATURE_TYPE

AmbiguityAction = Literal["ask_user", "skip", "proceed_with_flag"]

AGENT_A_NAME_MAX_LENGTH = 80
AGENT_A_SUMMARY_MAX_LENGTH = 300
AGENT_A_FEATURE_ID_PATTERN = r"^F-[0-9]{3}$"


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


def serialize_agent_a_output(output: AgentAOutput) -> dict[str, Any]:
    return output.model_dump(mode="json")
