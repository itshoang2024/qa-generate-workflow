from app.domain.models import (
    Feature,
    FeatureType,
    GDDSection,
    PipelineStage,
    Priority,
    QATask,
    Estimate,
    ReviewStatus,
    TestCase as DomainTestCase,
    TestCategory as DomainTestCategory,
    TestType as DomainTestType,
)
from app.services.validators import (
    validate_features,
    validate_features_with_routing,
    validate_tasks,
    validate_tasks_with_routing,
    validate_test_cases,
)


def test_validate_features_flags_missing_source_and_low_confidence() -> None:
    sections = [
        GDDSection(id="sec_1", run_id="run_1", section_id="§2.3", title="Tap", level=2),
    ]
    features = [
        Feature(
            id="feat_1",
            run_id="run_1",
            feature_id="F-001",
            name="Feature",
            summary="Summary",
            feature_type=FeatureType.GAMEPLAY_LOGIC,
            source_sections=["§9.9"],
            assignee="Ngoc Anh",
            confidence=0.5,
        )
    ]

    issues = validate_features("run_1", features, sections)

    assert {issue.code for issue in issues} >= {"missing_source_section", "low_confidence_feature"}
    assert any(issue.stage == PipelineStage.S3_VALIDATION_A for issue in issues)


def test_validate_tasks_flags_bad_assignee_duplicate_and_low_confidence() -> None:
    sections = [
        GDDSection(id="sec_1", run_id="run_1", section_id="§2.3", title="Tap", level=2),
    ]
    features = [
        Feature(
            id="feat_1",
            run_id="run_1",
            feature_id="F-001",
            name="Feature",
            summary="Summary",
            feature_type=FeatureType.GAMEPLAY_LOGIC,
            source_sections=["§2.3"],
            assignee="Ngoc Anh",
            confidence=0.9,
        )
    ]
    tasks = [
        _task("T-001", "Verify Hint booster cost", "Unknown"),
        _task("T-002", "Verify Hint booster costs", "Ngoc Anh"),
    ]

    issues = validate_tasks("run_1", tasks, features, sections)

    assert {issue.code for issue in issues} >= {
        "invalid_assignee",
        "low_confidence_task",
        "duplicate_task_candidate",
    }


def test_validate_features_with_routing_assigns_hil1_lanes() -> None:
    sections = [
        GDDSection(id="sec_1", run_id="run_1", section_id="Â§2.3", title="Tap", level=2),
    ]
    features = [
        _feature("F-001", "Batch feature", 0.7),
        _feature("F-002", "Blocked feature", 0.5),
    ]

    validate_features_with_routing("run_1", features, sections)

    assert features[0].review_status == ReviewStatus.NEEDS_REVIEW
    assert features[0].lane == "BATCH"
    assert features[1].review_status == ReviewStatus.BLOCKED
    assert features[1].lane == "BLOCK"


def test_validate_tasks_with_routing_blocks_duplicate_candidates() -> None:
    sections = [
        GDDSection(id="sec_1", run_id="run_1", section_id="Â§2.3", title="Tap", level=2),
    ]
    features = [_feature("F-001", "Feature", 0.9)]
    tasks = [
        _task("T-001", "Verify Hint booster cost", "Ngoc Anh"),
        _task("T-002", "Verify Hint booster costs", "Ngoc Anh"),
    ]

    validate_tasks_with_routing("run_1", tasks, features, sections)

    assert {task.review_status for task in tasks} == {ReviewStatus.BLOCKED}
    assert {task.lane for task in tasks} == {"BLOCK"}


def test_validate_test_cases_requires_all_categories() -> None:
    sections = [
        GDDSection(id="sec_1", run_id="run_1", section_id="§2.3", title="Tap", level=2),
    ]
    tasks = [_task("T-001", "Verify tap", "Ngoc Anh")]
    test_cases = [
        DomainTestCase(
            id="tc_1",
            run_id="run_1",
            test_case_id="TC-0001",
            title="Positive",
            type=DomainTestType.FUNCTIONAL,
            category=DomainTestCategory.POSITIVE,
            priority=Priority.P0,
            preconditions=[],
            steps=[],
            expected_result="Expected result",
            related_task_id="T-001",
            source_sections=["§2.3"],
            external_id="snake-escape-F-001-T-01-TC-01",
        )
    ]

    issues = validate_test_cases("run_1", test_cases, tasks, sections)

    assert any(issue.code == "missing_test_case_category" for issue in issues)


def _feature(feature_id: str, name: str, confidence: float) -> Feature:
    return Feature(
        id=f"feat_{feature_id}",
        run_id="run_1",
        feature_id=feature_id,
        name=name,
        summary="Summary",
        feature_type=FeatureType.GAMEPLAY_LOGIC,
        source_sections=["Â§2.3"],
        assignee="Ngoc Anh",
        confidence=confidence,
    )


def _task(task_id: str, title: str, assignee: str) -> QATask:
    return QATask(
        id=f"task_{task_id}",
        run_id="run_1",
        task_id=task_id,
        story_id="S-001",
        epic_id="E-001",
        feature_id="F-001",
        title=title,
        description="Task description",
        assignee=assignee,
        priority=Priority.P0,
        estimate=Estimate.S,
        source_sections=["§2.3"],
        external_id=f"snake-escape-F-001-{task_id}",
        confidence=0.7,
    )
