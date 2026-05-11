from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, cast

from app.domain.models import (
    Epic,
    PipelineStage,
    QATask,
    Story,
    ValidationIssue,
    ValidationSeverity,
)
from app.services.agents import AgentClient, AgentOutputValidationError
from app.services.validators import validate_agent_b_plan_coverage

MAX_AGENT_B_ATTEMPTS = 3


@dataclass(frozen=True)
class AgentBAttemptLog:
    attempt: int
    outcome: str
    issue_codes: list[str]
    missing_feature_ids: list[str]
    missing_epic_ids: list[str]
    provider: str
    message: str | None = None

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentBRetryResult:
    output: dict[str, list[Any]]
    coverage_issues: list[ValidationIssue]
    attempts: list[AgentBAttemptLog]
    exhausted: bool = False

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    def attempt_log(self) -> list[dict[str, Any]]:
        return [attempt.model_dump() for attempt in self.attempts]


def run_agent_b_with_retries(
    *,
    agent_client: AgentClient,
    run_id: str,
    hil1_context: dict[str, object],
    max_attempts: int = MAX_AGENT_B_ATTEMPTS,
) -> AgentBRetryResult:
    attempts: list[AgentBAttemptLog] = []
    validation_feedback: list[dict[str, Any]] | None = None
    last_output = _empty_agent_b_output()
    last_issues: list[ValidationIssue] = []

    for attempt in range(1, max_attempts + 1):
        attempt_context = _context_with_feedback(hil1_context, validation_feedback)
        output = agent_client.plan_qa_tasks(run_id, hil_context=attempt_context)
        provider = agent_client.provider_for("plan_qa_tasks")
        epics, stories, tasks = _plan_items_from_output(output)
        coverage_issues = validate_agent_b_plan_coverage(
            run_id,
            epics=epics,
            stories=stories,
            tasks=tasks,
            hil1_context=hil1_context,
        )
        last_output = output
        last_issues = coverage_issues
        fallback_message = (
            "OpenAI Agent B fell back to the static mock planner; the fallback plan "
            "cannot cover this run's approved HIL-1 scope."
            if coverage_issues and _is_openai_mock_fallback(provider)
            else None
        )
        attempts.append(
            AgentBAttemptLog(
                attempt=attempt,
                outcome=(
                    "accepted"
                    if not coverage_issues
                    else "provider_fallback_incomplete"
                    if fallback_message
                    else "coverage_retry"
                ),
                issue_codes=sorted({issue.code for issue in coverage_issues}),
                missing_feature_ids=_target_ids(coverage_issues, "feature"),
                missing_epic_ids=_target_ids(coverage_issues, "epic"),
                provider=provider,
                message=fallback_message,
            )
        )

        if not coverage_issues:
            return AgentBRetryResult(
                output=output,
                coverage_issues=[],
                attempts=attempts,
            )

        if attempt == max_attempts or fallback_message:
            break

        validation_feedback = _feedback_from_issues(coverage_issues)

    exhausted_issue = ValidationIssue(
        run_id=run_id,
        target_type="agent",
        target_id="Agent B",
        severity=ValidationSeverity.S1_CRITICAL,
        code="agent_b_coverage_exhausted",
        message=(
            f"Agent B coverage validation still failed after {len(attempts)} attempts; "
            "block Sync-A/B until the plan covers all approved HIL-1 scope."
        ),
        stage=PipelineStage.S5_VALIDATION_B_SYNC,
    )
    return AgentBRetryResult(
        output=last_output,
        coverage_issues=[*last_issues, exhausted_issue],
        attempts=attempts,
        exhausted=True,
    )


def _plan_items_from_output(
    output: dict[str, list[Any]],
) -> tuple[list[Epic], list[Story], list[QATask]]:
    epics = output.get("epics")
    stories = output.get("stories")
    tasks = output.get("tasks")
    if not isinstance(epics, list) or not all(isinstance(epic, Epic) for epic in epics):
        raise AgentOutputValidationError("Agent B output must include a list of Epic models.")
    if not isinstance(stories, list) or not all(
        isinstance(story, Story) for story in stories
    ):
        raise AgentOutputValidationError("Agent B output must include a list of Story models.")
    if not isinstance(tasks, list) or not all(isinstance(task, QATask) for task in tasks):
        raise AgentOutputValidationError("Agent B output must include a list of QATask models.")
    return cast(list[Epic], epics), cast(list[Story], stories), cast(list[QATask], tasks)


def _context_with_feedback(
    hil1_context: dict[str, object],
    validation_feedback: list[dict[str, Any]] | None,
) -> dict[str, object]:
    if not validation_feedback:
        return hil1_context
    return {
        **hil1_context,
        "validation_feedback": validation_feedback,
    }


def _feedback_from_issues(issues: list[ValidationIssue]) -> list[dict[str, Any]]:
    return [
        {
            "code": issue.code,
            "target_type": issue.target_type,
            "target_id": issue.target_id,
            "message": issue.message,
        }
        for issue in issues
    ]


def _target_ids(issues: list[ValidationIssue], target_type: str) -> list[str]:
    return sorted(
        {issue.target_id for issue in issues if issue.target_type == target_type}
    )


def _is_openai_mock_fallback(provider: str) -> bool:
    return provider.startswith("mock_after_openai_")


def _empty_agent_b_output() -> dict[str, list[Any]]:
    return {"epics": [], "stories": [], "tasks": []}
