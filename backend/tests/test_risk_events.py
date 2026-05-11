from app.domain.models import (
    PipelineStage,
    RiskEvent,
    RiskSeverity,
    ValidationIssue,
    ValidationSeverity,
)
from app.services.risk_events import kill_switch_state, risk_events_from_validation_issues


def test_risk_events_are_derived_from_validation_issue_codes() -> None:
    issue = ValidationIssue(
        run_id="run_1",
        target_type="task",
        target_id="T-001",
        severity=ValidationSeverity.S2_RECOVERABLE,
        code="duplicate_task_candidate",
        message="Duplicate task candidate.",
        stage=PipelineStage.S5_VALIDATION_B_SYNC,
    )

    events = risk_events_from_validation_issues([issue])

    assert len(events) == 1
    assert events[0].code == "duplicate_task_candidate"
    assert events[0].severity == RiskSeverity.S2


def test_kill_switch_trips_at_critical_risk_threshold() -> None:
    events = [
        RiskEvent(
            run_id="run_1",
            severity=RiskSeverity.S1,
            code=f"critical_{index}",
            summary="Critical risk.",
            target_type="run",
            target_id="run_1",
            owner_action="Inspect before continuing.",
        )
        for index in range(3)
    ]

    state = kill_switch_state(events)

    assert state["tripped"] is True
    assert state["s1_risk_count"] == 3
