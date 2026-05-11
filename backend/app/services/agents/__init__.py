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
