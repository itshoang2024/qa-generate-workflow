from app.domain.models import (
    Feature,
    FeatureType,
    GDDSection,
    PipelineStage,
    Priority,
    QATask,
    Estimate,
    ReviewStatus,
    Epic,
    Story,
    TestCase as DomainTestCase,
    TestCategory as DomainTestCategory,
    TestType as DomainTestType,
)
from app.services.validators import (
    validate_agent_b1_epic_coverage,
    validate_agent_b2_story_coverage,
    validate_agent_b3_full_plan,
    validate_agent_b_plan_coverage,
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


def test_validate_agent_b_plan_coverage_flags_missing_approved_features_and_epics() -> None:
    epics = [_epic("HIL1-GAMEPLAY-LOGIC", ["F-001"])]
    stories = [_story("S-001", "HIL1-GAMEPLAY-LOGIC", "F-001")]
    tasks = [_task("T-001", "Verify tap", "Ngoc Anh")]
    hil1_context = {
        "approved_feature_ids": ["F-001", "F-002", "F-003"],
        "approved_features": [
            _approved_feature("F-001", "gameplay_logic"),
            _approved_feature("F-002", "ui_layout"),
            _approved_feature("F-003", "economy"),
        ],
        "epic_structure": {
            "epics": [
                {
                    "epic_id": "HIL1-GAMEPLAY-LOGIC",
                    "title": "Gameplay Logic Scope",
                    "feature_ids": ["F-001"],
                },
                {
                    "epic_id": "HIL1-UI-LAYOUT",
                    "title": "Ui Layout Scope",
                    "feature_ids": ["F-002"],
                },
                {
                    "epic_id": "HIL1-ECONOMY",
                    "title": "Economy Scope",
                    "feature_ids": ["F-003"],
                },
            ]
        },
    }

    issues = validate_agent_b_plan_coverage(
        "run_1",
        epics=epics,
        stories=stories,
        tasks=tasks,
        hil1_context=hil1_context,
    )

    assert {
        (issue.code, issue.target_type, issue.target_id)
        for issue in issues
    } >= {
        ("missing_agent_b_feature_coverage", "feature", "F-002"),
        ("missing_agent_b_feature_coverage", "feature", "F-003"),
        ("missing_agent_b_epic_coverage", "epic", "HIL1-UI-LAYOUT"),
        ("missing_agent_b_epic_coverage", "epic", "HIL1-ECONOMY"),
    }


def test_validate_agent_b1_epic_coverage_flags_missing_and_unknown_features() -> None:
    epics = [_epic("E-CORE", ["F-001", "F-999"])]
    hil1_context = {
        "approved_feature_ids": ["F-001", "F-002"],
        "approved_features": [
            _approved_feature("F-001", "gameplay_logic"),
            _approved_feature("F-002", "ui_layout"),
        ],
    }

    issues = validate_agent_b1_epic_coverage("run_1", epics, hil1_context)

    assert {
        (issue.code, issue.target_type, issue.target_id)
        for issue in issues
    } >= {
        ("missing_b1_feature_coverage", "feature", "F-002"),
        ("unknown_b1_feature_reference", "epic", "E-CORE"),
    }


def test_validate_agent_b2_story_coverage_flags_missing_feature_story() -> None:
    epic = _epic("E-CORE", ["F-001", "F-002"])
    features = [_feature("F-001", "One", 0.9), _feature("F-002", "Two", 0.9)]
    stories = [_story("S-001", "E-CORE", "F-001")]

    issues = validate_agent_b2_story_coverage("run_1", epic, stories, features)

    assert {issue.code for issue in issues} >= {
        "missing_b2_story_for_feature",
        "b2_story_count_out_of_range",
    }


def test_validate_agent_b3_full_plan_flags_cross_story_duplicates() -> None:
    sections = [
        GDDSection(id="sec_1", run_id="run_1", section_id="Â§2.3", title="Tap", level=2),
    ]
    epics = [_epic("E-CORE", ["F-001"])]
    stories = [
        _story("S-001", "E-CORE", "F-001"),
        _story("S-002", "E-CORE", "F-001"),
    ]
    features = [_feature("F-001", "Feature", 0.9)]
    tasks = [
        _task("T-001", "Verify Hint booster cost", "Ngoc Anh"),
        _task("T-002", "Verify Hint booster costs", "Ngoc Anh").model_copy(
            update={"story_id": "S-002"}
        ),
    ]

    issues = validate_agent_b3_full_plan(
        "run_1",
        epics=epics,
        stories=stories,
        tasks=tasks,
        features=features,
        sections=sections,
    )

    assert "duplicate_task_cross_story" in {issue.code for issue in issues}
    assert {task.review_status for task in tasks} == {ReviewStatus.BLOCKED}


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


def test_validate_test_cases_flags_vague_phrases_and_unseeded_rng() -> None:
    sections = [
        GDDSection(id="sec_1", run_id="run_1", section_id="Â§2.3", title="Tap", level=2),
    ]
    tasks = [_task("T-001", "Verify daily challenge", "Ngoc Anh")]
    test_cases = [
        DomainTestCase(
            id="tc_1",
            run_id="run_1",
            test_case_id="TC-0001",
            title="Daily random level loads",
            type=DomainTestType.FUNCTIONAL,
            category=DomainTestCategory.POSITIVE,
            priority=Priority.P0,
            preconditions=["Player account is in a valid state"],
            steps=["Open daily challenge", "Start the random level"],
            expected_result="The daily challenge level loads.",
            related_task_id="T-001",
            source_sections=["Â§2.3"],
            external_id="snake-escape-F-001-T-01-TC-01",
            test_data={"board": "5x5"},
        )
    ]

    issues = validate_test_cases("run_1", test_cases, tasks, sections)

    assert {issue.code for issue in issues} >= {
        "forbidden_vague_phrase",
        "rng_without_seed",
    }


def test_validate_test_cases_flags_multi_assertion_expected_result() -> None:
    sections = [
        GDDSection(id="sec_1", run_id="run_1", section_id="Â§2.3", title="Tap", level=2),
    ]
    tasks = [_task("T-001", "Verify blocked tap", "Ngoc Anh")]
    test_cases = [
        DomainTestCase(
            id="tc_1",
            run_id="run_1",
            test_case_id="TC-0001",
            title="Blocked tap failure flow",
            type=DomainTestType.FUNCTIONAL,
            category=DomainTestCategory.POSITIVE,
            priority=Priority.P0,
            preconditions=["health=1", "snake_A blocked"],
            steps=["Tap snake_A"],
            expected_result="Health decreases to 0 and the failed popup appears.",
            related_task_id="T-001",
            source_sections=["Â§2.3"],
            external_id="snake-escape-F-001-T-01-TC-01",
            test_data={"health": 1, "snake": "snake_A"},
        )
    ]

    issues = validate_test_cases("run_1", test_cases, tasks, sections)

    assert "one_assertion_expected_result" in {issue.code for issue in issues}


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


def _epic(epic_id: str, feature_ids: list[str]) -> Epic:
    return Epic(
        id=f"epic_{epic_id}",
        run_id="run_1",
        epic_id=epic_id,
        title="Gameplay Logic Scope",
        description="Epic description",
        feature_ids=feature_ids,
        external_id=f"snake-escape-{epic_id}",
    )


def _story(story_id: str, epic_id: str, feature_id: str) -> Story:
    return Story(
        id=f"story_{story_id}",
        run_id="run_1",
        story_id=story_id,
        epic_id=epic_id,
        title="Story title",
        description="Story description",
        feature_id=feature_id,
        external_id=f"snake-escape-{epic_id}-{story_id}",
    )


def _approved_feature(feature_id: str, feature_type: str) -> dict[str, object]:
    return {
        "feature_id": feature_id,
        "feature_type": feature_type,
        "delta_status": None,
    }
