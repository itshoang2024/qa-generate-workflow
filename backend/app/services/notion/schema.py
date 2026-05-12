from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExpectedProperty:
    name: str
    allowed_types: frozenset[str]


EXPECTED_DATABASE_PROPERTIES: dict[str, tuple[ExpectedProperty, ...]] = {
    "epic": (
        ExpectedProperty("Title", frozenset({"title"})),
        ExpectedProperty("Description", frozenset({"rich_text"})),
        ExpectedProperty("Feature IDs", frozenset({"rich_text"})),
        ExpectedProperty("external_id", frozenset({"rich_text"})),
    ),
    "story": (
        ExpectedProperty("Title", frozenset({"title"})),
        ExpectedProperty("Description", frozenset({"rich_text"})),
        ExpectedProperty("Acceptance criteria", frozenset({"rich_text"})),
        ExpectedProperty("Feature", frozenset({"rich_text"})),
        ExpectedProperty("Epic", frozenset({"relation"})),
        ExpectedProperty("external_id", frozenset({"rich_text"})),
    ),
    "task": (
        ExpectedProperty("Task title", frozenset({"title"})),
        ExpectedProperty("Description", frozenset({"rich_text"})),
        ExpectedProperty("Feature name", frozenset({"rich_text"})),
        ExpectedProperty("Epic", frozenset({"relation"})),
        ExpectedProperty("Story", frozenset({"relation"})),
        ExpectedProperty("Priority", frozenset({"select"})),
        ExpectedProperty("Estimate", frozenset({"select"})),
        ExpectedProperty("Suggested assignee", frozenset({"people", "rich_text", "select"})),
        ExpectedProperty("Status", frozenset({"select", "status"})),
        ExpectedProperty("external_id", frozenset({"rich_text"})),
        ExpectedProperty("Source sections", frozenset({"rich_text"})),
        ExpectedProperty("Confidence", frozenset({"number"})),
    ),
    "test_case": (
        ExpectedProperty("Title", frozenset({"title"})),
        ExpectedProperty("Type", frozenset({"select"})),
        ExpectedProperty("Category", frozenset({"select"})),
        ExpectedProperty("Priority", frozenset({"select"})),
        ExpectedProperty("Related task", frozenset({"relation"})),
        ExpectedProperty("Preconditions", frozenset({"rich_text"})),
        ExpectedProperty("Test data", frozenset({"rich_text"})),
        ExpectedProperty("Steps", frozenset({"rich_text"})),
        ExpectedProperty("Expected result", frozenset({"rich_text"})),
        ExpectedProperty("Source sections", frozenset({"rich_text"})),
        ExpectedProperty("external_id", frozenset({"rich_text"})),
        ExpectedProperty("Status", frozenset({"select", "status"})),
    ),
}
