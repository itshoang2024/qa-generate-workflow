from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.domain.models import GDDSection, QATask, RunMode, TestCase


class AgentOutputValidationError(ValueError):
    """Raised when an agent response cannot be parsed or schema-validated."""


class AgentClient(ABC):
    provider = "unknown"

    def provider_for(self, operation: str) -> str:
        return self.provider

    # ------------------------------------------------------------------
    # Existing methods (S2 Agent A, legacy bundled S4 Agent B, S6 Agent C).
    # ------------------------------------------------------------------

    @abstractmethod
    def analyze_gdd(
        self,
        run_id: str,
        sections: list[GDDSection],
        *,
        mode: RunMode = RunMode.NEW_GAME,
        delta_report: dict[str, Any] | None = None,
        validation_feedback: list[dict[str, Any]] | None = None,
        target_section_ids: list[str] | None = None,
    ) -> dict[str, object]: ...

    @abstractmethod
    def plan_qa_tasks(
        self,
        run_id: str,
        *,
        hil_context: dict[str, Any] | None = None,
    ) -> dict[str, list[Any]]: ...

    @abstractmethod
    def generate_test_cases(self, run_id: str, tasks: list[QATask]) -> list[TestCase]: ...

    # ------------------------------------------------------------------
    # Phase 1.8 — hierarchical Agent B (B1 / B2 / B3).
    #
    # Concrete subclasses override these to implement S4.1, S4.2 (fan-out
    # per epic), and S4.3 (fan-out per story). Default implementations raise
    # NotImplementedError so existing MockAgentClient and OpenAIAgentClient
    # keep compiling; promote to @abstractmethod once both adapters land.
    #
    # See Task-2-Agent-prompts-JSON.md sections "Agent B1", "Agent B2",
    # "Agent B3" for prompt + JSON schema contracts.
    # ------------------------------------------------------------------

    def plan_epics(
        self,
        run_id: str,
        *,
        hil_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Agent B1 — Epic Planner (S4.1).

        Input contract (from `build_agent_b1_input` in `contracts.py`):
          - hil_context["approved_features"]: list of Agent A feature dicts that
            passed HIL-1 approval.
          - hil_context["epic_candidates"]: deterministic feature_type group
            suggestions from `_hil1_epic_structure` in PipelineService.
          - hil_context["mode"], hil_context["project_id"], hil_context["kb_rules"].

        Output contract (validated by `AgentB1Output` in `contracts.py`):
          {
              "epics": [
                  {
                      "epic_id": "E-CORE-GAMEPLAY",
                      "title": "...",
                      "description": "...",
                      "feature_ids": ["F-001", "F-002"],
                      "rationale": "...",
                      "external_id": "snake-escape-E-CORE-GAMEPLAY",
                      "delta_status": "NEW" | "MODIFIED" | "UNCHANGED" | "REMOVED" | None,
                  },
                  ...
              ]
          }

        Invariants the implementation must guarantee:
          1. Every approved feature_id appears in exactly one epic
             (cross-cutting allowed in up to 3).
          2. epic_id matches r"^E-[A-Z0-9-]+$".
          3. external_id follows "<project_id>-E-<epic_short>".
        """
        raise NotImplementedError("Phase 1.8: subclass must override plan_epics().")

    def plan_stories(
        self,
        run_id: str,
        *,
        epic: dict[str, Any],
        features: list[dict[str, Any]],
        source_text: dict[str, str],
        story_seq_offset: int,
    ) -> dict[str, Any]:
        """Agent B2 — Story Planner (S4.2), called once per epic.

        Input contract (from `build_agent_b2_input` in `contracts.py`):
          - epic: one epic dict from `plan_epics()` output.
          - features: subset of `approved_features` whose feature_id ∈ epic["feature_ids"].
          - source_text: {section_id: verbatim_text} for every section referenced
            by `features[*].source_sections`. Required for acceptance-criterion
            grounding (keyword overlap check in V-B2).
          - story_seq_offset: starting story_seq for this epic so parallel
            fan-out calls do not collide on story_id.

        Output contract (validated by `AgentB2Output` in `contracts.py`):
          {
              "epic_id": epic["epic_id"],
              "stories": [
                  {
                      "story_id": "S-001",
                      "title": "As a player, ...",
                      "description": "...",
                      "feature_id": "F-001",
                      "acceptance_criteria": ["...", "..."],
                      "external_id": "<epic.external_id>-S-<seq>",
                  },
                  ...
              ]
          }

        Invariants:
          1. Every feature in `features` produces ≥1 story (story.feature_id ==
             feature.feature_id).
          2. story_id is contiguous starting from story_seq_offset.
          3. external_id = f"{epic['external_id']}-S-{seq:03d}".
        """
        raise NotImplementedError("Phase 1.8: subclass must override plan_stories().")

    def plan_tasks(
        self,
        run_id: str,
        *,
        story: dict[str, Any],
        feature: dict[str, Any],
        source_text: dict[str, str],
        task_seq_offset: int,
        past_corrections: list[dict[str, Any]] | None = None,
        existing_tasks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Agent B3 — Task Planner (S4.3), called once per story.

        Input contract (from `build_agent_b3_input` in `contracts.py`):
          - story: one story dict from `plan_stories()` output.
          - feature: the single feature this story belongs to.
          - source_text: {section_id: verbatim_text} for every section in
            feature["source_sections"]. Required for description grounding.
          - task_seq_offset: starting task_seq for this story's feature so
            parallel fan-out calls do not collide on task_id / external_id.
            Note: seq is per (project_id, feature_id), NOT per story.
          - past_corrections: top-K relevant correction records for this
            feature_type from project long-term memory (optional).
          - existing_tasks: DELTA mode only; reuse external_id when behavior
            matches.

        Output contract (validated by `AgentB3Output` in `contracts.py`):
          {
              "story_id": story["story_id"],
              "tasks": [
                  {
                      "task_id": "T-001",
                      "feature_id": story["feature_id"],
                      "title": "...",
                      "description": "...",
                      "assignee": "Ngọc Anh" | "Minh" | ...,
                      "priority": "P0" | "P1" | "P2",
                      "priority_justification": "...",
                      "estimate": "S" | "M" | "L",
                      "source_sections": ["§2.3"],
                      "external_id": "<project_id>-<feature_id>-T-<seq>",
                      "delta_status": "NEW" | "UPDATE_RETEST" | "ARCHIVE" | None,
                      "confidence": 0.0-1.0,
                  },
                  ...
              ]
          }

        Invariants:
          1. Every task.feature_id == story.feature_id.
          2. task.source_sections ⊆ feature.source_sections.
          3. Assignee is overwritten post-output by `QA_ASSIGNEE_BY_FEATURE_TYPE`
             lookup — do not trust AI's assignee.
          4. external_id seq is per (project_id, feature_id), allocated under
             a repository transaction/lock.
        """
        raise NotImplementedError("Phase 1.8: subclass must override plan_tasks().")
