from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.domain.models import GDDSection, QATask, TestCase


class AgentClient(ABC):
    @abstractmethod
    def analyze_gdd(self, run_id: str, sections: list[GDDSection]) -> dict[str, object]: ...

    @abstractmethod
    def plan_qa_tasks(self, run_id: str) -> dict[str, list[Any]]: ...

    @abstractmethod
    def generate_test_cases(self, run_id: str, tasks: list[QATask]) -> list[TestCase]: ...
