from __future__ import annotations

from collections import Counter

from app.domain.models import RiskEvent, RiskSeverity, ValidationIssue

RISK_RULES = {
    "missing_source_section": (
        RiskSeverity.S1,
        "Possible hallucination: generated artifact references a missing GDD section.",
        "QA Lead must inspect source traceability before downstream use.",
    ),
    "task_missing_source_section": (
        RiskSeverity.S1,
        "Possible hallucination: QA task references a missing GDD section.",
        "QA Lead must block or rewrite the task before sync.",
    ),
    "test_case_missing_source_section": (
        RiskSeverity.S1,
        "Possible hallucination: test case references a missing GDD section.",
        "Assignee must review the test case source trace before execution.",
    ),
    "uncovered_actionable_section": (
        RiskSeverity.S2,
        "Scope drift: actionable GDD section is not covered by a feature.",
        "QA Lead should decide whether to rerun Agent A or mark the section skipped.",
    ),
    "invalid_assignee": (
        RiskSeverity.S2,
        "Assignee mismatch: generated task owner is outside the seeded QA roster.",
        "Apply rule-based assignee mapping before sync.",
    ),
    "duplicate_task_candidate": (
        RiskSeverity.S2,
        "Duplicate task candidate detected by title similarity.",
        "QA Lead should merge, approve, or reject the duplicate candidate.",
    ),
}

KILL_SWITCH_S1_THRESHOLD = 3


def risk_events_from_validation_issues(issues: list[ValidationIssue]) -> list[RiskEvent]:
    events: list[RiskEvent] = []
    for issue in issues:
        rule = RISK_RULES.get(issue.code)
        if rule is None:
            continue
        severity, summary, owner_action = rule
        events.append(
            RiskEvent(
                run_id=issue.run_id,
                severity=severity,
                code=issue.code,
                summary=summary,
                target_type=issue.target_type,
                target_id=issue.target_id,
                owner_action=owner_action,
            )
        )
    return events


def kill_switch_state(events: list[RiskEvent]) -> dict[str, object]:
    counts = Counter(event.severity.value for event in events)
    s1_count = counts.get(RiskSeverity.S1.value, 0)
    return {
        "s1_risk_count": s1_count,
        "threshold": KILL_SWITCH_S1_THRESHOLD,
        "tripped": s1_count >= KILL_SWITCH_S1_THRESHOLD,
    }


def kill_switch_risk_event(run_id: str, state: dict[str, object]) -> RiskEvent:
    return RiskEvent(
        run_id=run_id,
        severity=RiskSeverity.S1,
        code="kill_switch_tripped",
        summary="Kill switch tripped because critical risk count reached the configured threshold.",
        target_type="run",
        target_id=run_id,
        owner_action=(
            "Stop downstream generation, inspect S1/S2 risk events, and rerun only after "
            f"the critical count is below {state['threshold']}."
        ),
    )
