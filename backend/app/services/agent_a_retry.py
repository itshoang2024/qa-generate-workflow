from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, cast

from pydantic import ValidationError

from app.domain.models import (
    Feature,
    GDDSection,
    PipelineStage,
    ReviewStatus,
    RunMode,
    ValidationIssue,
    ValidationSeverity,
)
from app.services.agents import AgentClient, AgentOutputValidationError
from app.services.validators import validate_features_with_routing

MAX_AGENT_A_ATTEMPTS = 3
RETRYABLE_AGENT_A_CODES = {
    "missing_source_section",
    "uncovered_actionable_section",
}


@dataclass(frozen=True)
class AgentAAttemptLog:
    attempt: int
    outcome: str
    issue_codes: list[str]
    target_section_ids: list[str]
    message: str | None = None

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentARetryResult:
    output: dict[str, object]
    issues: list[ValidationIssue]
    attempts: list[AgentAAttemptLog]
    exhausted: bool = False

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    def attempt_log(self) -> list[dict[str, Any]]:
        return [attempt.model_dump() for attempt in self.attempts]


def run_agent_a_with_retries(
    *,
    agent_client: AgentClient,
    run_id: str,
    sections: list[GDDSection],
    mode: RunMode,
    delta_report: dict[str, Any] | None,
    max_attempts: int = MAX_AGENT_A_ATTEMPTS,
) -> AgentARetryResult:
    attempts: list[AgentAAttemptLog] = []
    validation_feedback: list[dict[str, Any]] | None = None
    target_section_ids: list[str] | None = None
    merge_base_output: dict[str, object] | None = None
    last_output = _empty_agent_a_output(sections)
    last_issues: list[ValidationIssue] = []

    for attempt in range(1, max_attempts + 1):
        try:
            output = agent_client.analyze_gdd(
                run_id,
                sections,
                mode=mode,
                delta_report=delta_report,
                validation_feedback=validation_feedback,
                target_section_ids=target_section_ids,
            )
            if merge_base_output is not None and target_section_ids:
                output = _merge_agent_a_outputs(merge_base_output, output, sections)
            features = _features_from_output(output)
            output = _normalized_output(output, features, sections)
        except (AgentOutputValidationError, ValidationError) as exc:
            issue = _issue(
                run_id,
                "agent",
                "Agent A",
                ValidationSeverity.S2_RECOVERABLE,
                "agent_a_schema_failure",
                f"Agent A output failed schema validation: {exc}",
            )
            last_issues = [issue]
            attempts.append(
                AgentAAttemptLog(
                    attempt=attempt,
                    outcome="schema_failure",
                    issue_codes=[issue.code],
                    target_section_ids=target_section_ids or [],
                    message=str(exc),
                )
            )
            if attempt == max_attempts:
                return _exhausted_result(run_id, last_output, last_issues, attempts)
            validation_feedback = _feedback_from_issues(last_issues)
            target_section_ids = None
            merge_base_output = None
            continue

        issues = validate_features_with_routing(run_id, features, sections)
        retryable_issues = _retryable_issues(issues)
        last_output = output
        last_issues = issues
        attempts.append(
            AgentAAttemptLog(
                attempt=attempt,
                outcome="accepted" if not retryable_issues else "validation_retry",
                issue_codes=sorted({issue.code for issue in retryable_issues}),
                target_section_ids=target_section_ids or [],
            )
        )

        if not retryable_issues:
            return AgentARetryResult(output=output, issues=issues, attempts=attempts)

        if attempt == max_attempts:
            return _exhausted_result(run_id, output, issues, attempts)

        has_traceability_failure = any(
            issue.code == "missing_source_section" for issue in retryable_issues
        )
        uncovered_targets = [] if has_traceability_failure else _uncovered_section_targets(
            retryable_issues
        )
        validation_feedback = _feedback_from_issues(retryable_issues)
        target_section_ids = uncovered_targets or None
        merge_base_output = output if uncovered_targets else None

    return _exhausted_result(run_id, last_output, last_issues, attempts)


def _retryable_issues(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    return [issue for issue in issues if issue.code in RETRYABLE_AGENT_A_CODES]


def _uncovered_section_targets(issues: list[ValidationIssue]) -> list[str]:
    return sorted(
        {
            issue.target_id
            for issue in issues
            if issue.code == "uncovered_actionable_section" and issue.target_type == "section"
        }
    )


def _features_from_output(output: dict[str, object]) -> list[Feature]:
    raw_features = output.get("features")
    if not isinstance(raw_features, list) or not all(
        isinstance(feature, Feature) for feature in raw_features
    ):
        raise AgentOutputValidationError("Agent A output must include a list of Feature models.")
    return cast(list[Feature], raw_features)


def _normalized_output(
    output: dict[str, object],
    features: list[Feature],
    sections: list[GDDSection],
) -> dict[str, object]:
    return {
        **output,
        "features": features,
        "coverage_report": _coverage_report(features, sections),
    }


def _merge_agent_a_outputs(
    base_output: dict[str, object],
    retry_output: dict[str, object],
    sections: list[GDDSection],
) -> dict[str, object]:
    # Index base features first, then overlay retry features on top.
    # For features present in BOTH outputs (same feature_id), we keep the
    # retry version's metadata (which may have been improved) but take the
    # UNION of source_sections.  This prevents a retry attempt from silently
    # dropping section references that the base had already discovered,
    # which would shift coverage holes to different sections on each attempt.
    base_by_id: dict[str, Feature] = {
        f.feature_id: f for f in _features_from_output(base_output)
    }
    retry_by_id: dict[str, Feature] = {
        f.feature_id: f for f in _features_from_output(retry_output)
    }

    merged: dict[str, Feature] = {**base_by_id}
    for fid, retry_feat in retry_by_id.items():
        if fid in base_by_id:
            # Union source_sections so neither attempt loses its coverage.
            unioned = sorted(
                set(base_by_id[fid].source_sections) | set(retry_feat.source_sections)
            )
            merged[fid] = retry_feat.model_copy(update={"source_sections": unioned})
        else:
            merged[fid] = retry_feat

    merged_list = list(merged.values())
    return {
        **retry_output,
        "features": merged_list,
        "coverage_report": _coverage_report(merged_list, sections),
        "ambiguities": _merge_ambiguities(base_output, retry_output),
    }


def _merge_ambiguities(
    base_output: dict[str, object],
    retry_output: dict[str, object],
) -> list[object]:
    merged: list[object] = []
    seen: set[str] = set()
    for output in (base_output, retry_output):
        raw_ambiguities = output.get("ambiguities", [])
        if not isinstance(raw_ambiguities, list):
            continue
        for ambiguity in raw_ambiguities:
            key = repr(ambiguity)
            if key in seen:
                continue
            seen.add(key)
            merged.append(ambiguity)
    return merged


def _coverage_report(features: list[Feature], sections: list[GDDSection]) -> dict[str, object]:
    actionable = [section.section_id for section in sections if section.actionable]
    covered = sorted({source for feature in features for source in feature.source_sections})
    uncovered = sorted(set(actionable) - set(covered))
    return {
        "total_input_sections": len(actionable),
        "covered_sections": covered,
        "uncovered_sections": uncovered,
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


def _exhausted_result(
    run_id: str,
    output: dict[str, object],
    issues: list[ValidationIssue],
    attempts: list[AgentAAttemptLog],
) -> AgentARetryResult:
    features = output.get("features", [])
    if isinstance(features, list):
        blocked_feature_ids = {
            issue.target_id
            for issue in issues
            if issue.target_type == "feature"
            and issue.code in {"missing_source_section", "hallucination_suspect"}
        }
        for feature in features:
            if isinstance(feature, Feature) and feature.feature_id in blocked_feature_ids:
                feature.review_status = ReviewStatus.BLOCKED

    exhausted_issue = _issue(
        run_id,
        "agent",
        "Agent A",
        ValidationSeverity.S2_RECOVERABLE,
        "agent_a_retry_exhausted",
        f"Agent A validation still failed after {len(attempts)} attempts; route to HIL-1.",
    )
    return AgentARetryResult(
        output=output,
        issues=[*issues, exhausted_issue],
        attempts=attempts,
        exhausted=True,
    )


def _empty_agent_a_output(sections: list[GDDSection]) -> dict[str, object]:
    return {
        "features": [],
        "coverage_report": _coverage_report([], sections),
        "ambiguities": [],
    }


def _issue(
    run_id: str,
    target_type: str,
    target_id: str,
    severity: ValidationSeverity,
    code: str,
    message: str,
) -> ValidationIssue:
    return ValidationIssue(
        run_id=run_id,
        target_type=target_type,
        target_id=target_id,
        severity=severity,
        code=code,
        message=message,
        stage=PipelineStage.S3_VALIDATION_A,
    )
