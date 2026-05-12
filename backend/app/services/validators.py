from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher

from app.domain.models import (
    FEATURE_BATCH_CONFIDENCE_THRESHOLD,
    DeltaStatus,
    Epic,
    Feature,
    GDDSection,
    PipelineStage,
    QATask,
    ReviewStatus,
    Story,
    TestCase,
    TestCategory,
    derive_router_lane,
    ValidationIssue,
    ValidationSeverity,
)
from app.domain.qa_roster import QA_MEMBERS


def validate_features(
    run_id: str,
    features: list[Feature],
    sections: list[GDDSection],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    known_sections = {section.section_id for section in sections}
    actionable_sections = {section.section_id for section in sections if section.actionable}
    covered_sections = {source for feature in features for source in feature.source_sections}

    for feature in features:
        missing_sources = [source for source in feature.source_sections if source not in known_sections]
        if missing_sources:
            issues.append(
                _issue(
                    run_id,
                    "feature",
                    feature.feature_id,
                    ValidationSeverity.S1_CRITICAL,
                    "missing_source_section",
                    f"Feature references unknown source sections: {', '.join(missing_sources)}",
                    PipelineStage.S3_VALIDATION_A,
                )
            )
        if feature.confidence < 0.85:
            issues.append(
                _issue(
                    run_id,
                    "feature",
                    feature.feature_id,
                    ValidationSeverity.S2_RECOVERABLE,
                    "low_confidence_feature",
                    "Feature requires HIL-1 review because confidence is below 0.85.",
                    PipelineStage.S3_VALIDATION_A,
                )
            )

    for section_id in sorted(actionable_sections - covered_sections):
        issues.append(
            _issue(
                run_id,
                "section",
                section_id,
                ValidationSeverity.S3_INFORMATIONAL,
                "uncovered_actionable_section",
                "Actionable GDD section is not mapped to any feature in the mock Agent A output.",
                PipelineStage.S3_VALIDATION_A,
            )
        )

    for section in sections:
        for flag in section.flags:
            issues.append(
                _issue(
                    run_id,
                    "section",
                    section.section_id,
                    ValidationSeverity.S3_INFORMATIONAL,
                    "preflight_note",
                    flag,
                    PipelineStage.S1_CONTEXT_LOADER,
                )
            )

    return issues


def validate_features_with_routing(
    run_id: str,
    features: list[Feature],
    sections: list[GDDSection],
) -> list[ValidationIssue]:
    issues = validate_features(run_id, features, sections)
    blocked_feature_ids = {
        issue.target_id
        for issue in issues
        if issue.target_type == "feature"
        and issue.code in {"missing_source_section", "hallucination_suspect"}
    }
    for feature in features:
        if feature.feature_id in blocked_feature_ids:
            lane = "BLOCK"
        else:
            lane = derive_router_lane(
                feature.confidence,
                dedup_flag=feature.dedup_flag,
                cross_cutting_flag=feature.cross_cutting_flag,
                batch_threshold=FEATURE_BATCH_CONFIDENCE_THRESHOLD,
            )
        _apply_routing_status(feature, lane)
    return issues


def validate_tasks(
    run_id: str,
    tasks: list[QATask],
    features: list[Feature],
    sections: list[GDDSection],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    known_features = {feature.feature_id: feature for feature in features}
    known_sections = {section.section_id for section in sections}

    for task in tasks:
        feature = known_features.get(task.feature_id)
        if feature is None:
            issues.append(
                _issue(
                    run_id,
                    "task",
                    task.task_id,
                    ValidationSeverity.S1_CRITICAL,
                    "unknown_feature",
                    "Task references a feature_id that Agent A did not create.",
                    PipelineStage.S5_VALIDATION_B_SYNC,
                )
            )
        elif feature.cross_cutting_flag:
            task.cross_cutting_flag = True
        if task.assignee not in QA_MEMBERS:
            issues.append(
                _issue(
                    run_id,
                    "task",
                    task.task_id,
                    ValidationSeverity.S1_CRITICAL,
                    "invalid_assignee",
                    f"Task assignee '{task.assignee}' is not in the seeded QA roster.",
                    PipelineStage.S5_VALIDATION_B_SYNC,
                )
            )
        if any(source not in known_sections for source in task.source_sections):
            issues.append(
                _issue(
                    run_id,
                    "task",
                    task.task_id,
                    ValidationSeverity.S1_CRITICAL,
                    "task_missing_source_section",
                    "Task references a source section that does not exist in the parsed GDD.",
                    PipelineStage.S5_VALIDATION_B_SYNC,
                )
            )
        if task.confidence < 0.85:
            issues.append(
                _issue(
                    run_id,
                    "task",
                    task.task_id,
                    ValidationSeverity.S2_RECOVERABLE,
                    "low_confidence_task",
                    "Task requires HIL-2 review because confidence is below 0.85.",
                    PipelineStage.S5_VALIDATION_B_SYNC,
                )
            )

    issues.extend(_duplicate_task_issues(run_id, tasks))
    return issues


def validate_agent_b_plan_coverage(
    run_id: str,
    *,
    epics: list[Epic],
    stories: list[Story],
    tasks: list[QATask],
    hil1_context: dict[str, object],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    required_feature_ids = _required_agent_b_feature_ids(hil1_context)
    covered_feature_ids = {
        feature_id
        for feature_id in {
            *(story.feature_id for story in stories),
            *(task.feature_id for task in tasks),
        }
        if feature_id in required_feature_ids
    }

    for feature_id in sorted(required_feature_ids - covered_feature_ids):
        issues.append(
            _issue(
                run_id,
                "feature",
                feature_id,
                ValidationSeverity.S1_CRITICAL,
                "missing_agent_b_feature_coverage",
                (
                    "Agent B plan does not include a story or task for approved "
                    f"HIL-1 feature {feature_id}."
                ),
                PipelineStage.S5_VALIDATION_B_SYNC,
            )
        )

    generated_feature_ids = {
        feature_id
        for generated_feature_ids in _generated_feature_ids_by_epic(
            epics,
            stories,
            tasks,
        ).values()
        for feature_id in generated_feature_ids
    }
    for candidate in _hil1_epic_candidates(hil1_context):
        candidate_feature_ids = {
            feature_id
            for feature_id in candidate["feature_ids"]
            if feature_id in required_feature_ids
        }
        if not candidate_feature_ids:
            continue
        if candidate_feature_ids & generated_feature_ids:
            continue
        issues.append(
            _issue(
                run_id,
                "epic",
                candidate["epic_id"],
                ValidationSeverity.S1_CRITICAL,
                "missing_agent_b_epic_coverage",
                (
                    "Agent B plan does not represent HIL-1 epic candidate "
                    f"{candidate['title']} with features: "
                    f"{', '.join(sorted(candidate_feature_ids))}."
                ),
                PipelineStage.S5_VALIDATION_B_SYNC,
            )
        )

    return issues


def validate_agent_b1_epic_coverage(
    run_id: str,
    epics: list[Epic],
    hil1_context: dict[str, object],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    required_feature_ids = _required_agent_b_feature_ids(hil1_context)
    approved_features = _approved_features_by_id(hil1_context)
    occurrences: dict[str, list[str]] = defaultdict(list)

    for epic in epics:
        for feature_id in epic.feature_ids:
            if feature_id not in approved_features:
                issues.append(
                    _issue(
                        run_id,
                        "epic",
                        epic.epic_id,
                        ValidationSeverity.S1_CRITICAL,
                        "unknown_b1_feature_reference",
                        f"Agent B1 epic references unknown or unapproved feature {feature_id}.",
                        PipelineStage.S4_1_AGENT_B_EPICS,
                    )
                )
                continue
            occurrences[feature_id].append(epic.epic_id)

    for feature_id in sorted(required_feature_ids - set(occurrences)):
        issues.append(
            _issue(
                run_id,
                "feature",
                feature_id,
                ValidationSeverity.S1_CRITICAL,
                "missing_b1_feature_coverage",
                f"Agent B1 did not place approved feature {feature_id} in any epic.",
                PipelineStage.S4_1_AGENT_B_EPICS,
            )
        )

    for feature_id, epic_ids in sorted(occurrences.items()):
        feature = approved_features.get(feature_id, {})
        cross_cutting = bool(feature.get("cross_cutting_flag")) or (
            feature.get("feature_type") == "cross_cutting"
        )
        allowed_count = 3 if cross_cutting else 1
        if len(epic_ids) > allowed_count:
            issues.append(
                _issue(
                    run_id,
                    "feature",
                    feature_id,
                    ValidationSeverity.S2_RECOVERABLE,
                    "extra_b1_feature_coverage",
                    (
                        f"Agent B1 placed feature {feature_id} in {len(epic_ids)} epics; "
                        f"allowed maximum is {allowed_count}."
                    ),
                    PipelineStage.S4_1_AGENT_B_EPICS,
                )
            )

    return issues


def validate_agent_b2_story_coverage(
    run_id: str,
    epic: Epic,
    stories: list[Story],
    features: list[Feature],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    required_feature_ids = {feature.feature_id for feature in features}
    covered_feature_ids = {
        story.feature_id
        for story in stories
        if story.epic_id == epic.epic_id and story.feature_id in required_feature_ids
    }

    for feature_id in sorted(required_feature_ids - covered_feature_ids):
        issues.append(
            _issue(
                run_id,
                "feature",
                feature_id,
                ValidationSeverity.S2_RECOVERABLE,
                "missing_b2_story_for_feature",
                (
                    f"Agent B2 did not produce a story for feature {feature_id} "
                    f"inside epic {epic.epic_id}."
                ),
                PipelineStage.S4_2_AGENT_B_STORIES,
            )
        )

    story_count = len([story for story in stories if story.epic_id == epic.epic_id])
    min_count = len(required_feature_ids)
    max_count = max(min_count * 2, 1)
    if required_feature_ids and not (min_count <= story_count <= max_count):
        issues.append(
            _issue(
                run_id,
                "epic",
                epic.epic_id,
                ValidationSeverity.S2_RECOVERABLE,
                "b2_story_count_out_of_range",
                (
                    f"Agent B2 produced {story_count} story item(s) for {min_count} "
                    f"feature(s); expected {min_count}..{max_count}."
                ),
                PipelineStage.S4_2_AGENT_B_STORIES,
            )
        )

    return issues


def validate_agent_b3_full_plan(
    run_id: str,
    *,
    epics: list[Epic],
    stories: list[Story],
    tasks: list[QATask],
    features: list[Feature],
    sections: list[GDDSection],
) -> list[ValidationIssue]:
    issues = validate_tasks(run_id, tasks, features, sections)
    issues.extend(_cross_scope_duplicate_task_issues(run_id, tasks))
    for task in tasks:
        lane = derive_router_lane(
            task.confidence,
            dedup_flag=task.dedup_flag,
            cross_cutting_flag=task.cross_cutting_flag,
        )
        _apply_routing_status(task, lane)
    issues.extend(_missing_task_story_links(run_id, stories, tasks))
    issues.extend(_missing_story_epic_links(run_id, epics, stories))
    return issues


def validate_tasks_with_routing(
    run_id: str,
    tasks: list[QATask],
    features: list[Feature],
    sections: list[GDDSection],
) -> list[ValidationIssue]:
    issues = validate_tasks(run_id, tasks, features, sections)
    for task in tasks:
        lane = derive_router_lane(
            task.confidence,
            dedup_flag=task.dedup_flag,
            cross_cutting_flag=task.cross_cutting_flag,
        )
        _apply_routing_status(task, lane)
    return issues


def _required_agent_b_feature_ids(hil1_context: dict[str, object]) -> set[str]:
    raw_approved_ids = hil1_context.get("approved_feature_ids", [])
    approved_id_items = raw_approved_ids if isinstance(raw_approved_ids, list) else []
    raw_features = hil1_context.get("approved_features", [])
    feature_items = raw_features if isinstance(raw_features, list) else []
    approved_ids = {
        feature_id
        for feature_id in approved_id_items
        if isinstance(feature_id, str)
    }
    unchanged_ids = {
        feature["feature_id"]
        for feature in feature_items
        if isinstance(feature, dict)
        and isinstance(feature.get("feature_id"), str)
        and feature.get("delta_status") == DeltaStatus.UNCHANGED.value
    }
    return approved_ids - unchanged_ids


def _approved_features_by_id(hil1_context: dict[str, object]) -> dict[str, dict[str, object]]:
    raw_features = hil1_context.get("approved_features", [])
    if not isinstance(raw_features, list):
        return {}
    features: dict[str, dict[str, object]] = {}
    for raw_feature in raw_features:
        if not isinstance(raw_feature, dict):
            continue
        feature_id = raw_feature.get("feature_id")
        if isinstance(feature_id, str):
            features[feature_id] = raw_feature
    for feature_id in _required_agent_b_feature_ids(hil1_context):
        features.setdefault(feature_id, {"feature_id": feature_id})
    return features


def _hil1_epic_candidates(hil1_context: dict[str, object]) -> list[dict[str, object]]:
    epic_structure = hil1_context.get("epic_structure", {})
    raw_epics = epic_structure.get("epics", []) if isinstance(epic_structure, dict) else []
    candidates: list[dict[str, object]] = []
    for raw_epic in raw_epics:
        if not isinstance(raw_epic, dict):
            continue
        raw_feature_ids = raw_epic.get("feature_ids", [])
        feature_ids = [
            feature_id for feature_id in raw_feature_ids if isinstance(feature_id, str)
        ] if isinstance(raw_feature_ids, list) else []
        epic_id = raw_epic.get("epic_id")
        title = raw_epic.get("title")
        if isinstance(epic_id, str) and isinstance(title, str) and feature_ids:
            candidates.append(
                {
                    "epic_id": epic_id,
                    "title": title,
                    "feature_ids": feature_ids,
                }
            )
    return candidates


def _generated_feature_ids_by_epic(
    epics: list[Epic],
    stories: list[Story],
    tasks: list[QATask],
) -> dict[str, set[str]]:
    generated_by_epic = {
        epic.epic_id: {feature_id for feature_id in epic.feature_ids}
        for epic in epics
    }
    for story in stories:
        generated_by_epic.setdefault(story.epic_id, set()).add(story.feature_id)
    for task in tasks:
        generated_by_epic.setdefault(task.epic_id, set()).add(task.feature_id)
    return generated_by_epic


def validate_test_cases(
    run_id: str,
    test_cases: list[TestCase],
    tasks: list[QATask],
    sections: list[GDDSection],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    known_tasks = {task.task_id for task in tasks}
    known_sections = {section.section_id for section in sections}
    categories_by_task: dict[str, set[TestCategory]] = defaultdict(set)

    for test_case in test_cases:
        categories_by_task[test_case.related_task_id].add(test_case.category)
        if test_case.related_task_id not in known_tasks:
            issues.append(
                _issue(
                    run_id,
                    "test_case",
                    test_case.test_case_id,
                    ValidationSeverity.S1_CRITICAL,
                    "unknown_related_task",
                    "Test case references a task_id that Agent B did not create.",
                    PipelineStage.S7_VALIDATION_C_SYNC,
                )
            )
        if any(source not in known_sections for source in test_case.source_sections):
            issues.append(
                _issue(
                    run_id,
                    "test_case",
                    test_case.test_case_id,
                    ValidationSeverity.S1_CRITICAL,
                    "test_case_missing_source_section",
                    "Test case references a source section that does not exist in the parsed GDD.",
                    PipelineStage.S7_VALIDATION_C_SYNC,
                )
            )
        if test_case.confidence < 0.85:
            issues.append(
                _issue(
                    run_id,
                    "test_case",
                    test_case.test_case_id,
                    ValidationSeverity.S2_RECOVERABLE,
                    "low_confidence_test_case",
                    "Test case requires HIL-3 review because confidence is below 0.85.",
                    PipelineStage.S7_VALIDATION_C_SYNC,
                )
            )

    required_categories = set(TestCategory)
    for task_id in known_tasks:
        missing = required_categories - categories_by_task[task_id]
        if missing:
            issues.append(
                _issue(
                    run_id,
                    "task",
                    task_id,
                    ValidationSeverity.S2_RECOVERABLE,
                    "missing_test_case_category",
                    f"Task is missing test case categories: {', '.join(sorted(m.value for m in missing))}",
                    PipelineStage.S7_VALIDATION_C_SYNC,
                )
            )

    return issues


def validate_test_cases_with_routing(
    run_id: str,
    test_cases: list[TestCase],
    tasks: list[QATask],
    sections: list[GDDSection],
) -> list[ValidationIssue]:
    issues = validate_test_cases(run_id, test_cases, tasks, sections)
    for test_case in test_cases:
        lane = derive_router_lane(
            test_case.confidence,
            dedup_flag=test_case.dedup_flag,
            cross_cutting_flag=test_case.cross_cutting_flag,
        )
        _apply_routing_status(test_case, lane)
    return issues


def _duplicate_task_issues(run_id: str, tasks: list[QATask]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for index, task in enumerate(tasks):
        for other in tasks[index + 1 :]:
            similarity = SequenceMatcher(
                None,
                task.title.lower(),
                other.title.lower(),
            ).ratio()
            if similarity >= 0.85:
                task.dedup_flag = True
                other.dedup_flag = True
                issues.append(
                    _issue(
                        run_id,
                        "task",
                        task.task_id,
                        ValidationSeverity.S2_RECOVERABLE,
                        "duplicate_task_candidate",
                        (
                            f"Task is similar to {other.task_id} "
                            f"(title similarity {similarity:.2f})."
                        ),
                        PipelineStage.S5_VALIDATION_B_SYNC,
                    )
                )
    return issues


def _cross_scope_duplicate_task_issues(
    run_id: str,
    tasks: list[QATask],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    emitted: set[tuple[str, str, str]] = set()
    for index, task in enumerate(tasks):
        for other in tasks[index + 1 :]:
            similarity = SequenceMatcher(
                None,
                task.title.lower(),
                other.title.lower(),
            ).ratio()
            if similarity < 0.85:
                continue
            scopes: list[tuple[str, str]] = []
            if task.story_id != other.story_id:
                scopes.append(("duplicate_task_cross_story", other.story_id))
            if task.epic_id != other.epic_id:
                scopes.append(("duplicate_task_cross_epic", other.epic_id))
            for code, other_scope_id in scopes:
                dedup_key = (task.task_id, other.task_id, code)
                if dedup_key in emitted:
                    continue
                emitted.add(dedup_key)
                task.dedup_flag = True
                other.dedup_flag = True
                issues.append(
                    _issue(
                        run_id,
                        "task",
                        task.task_id,
                        ValidationSeverity.S2_RECOVERABLE,
                        code,
                        (
                            f"Task is similar to {other.task_id} in {other_scope_id} "
                            f"(title similarity {similarity:.2f})."
                        ),
                        PipelineStage.S5_VALIDATION_B_SYNC,
                    )
                )
    return issues


def _missing_task_story_links(
    run_id: str,
    stories: list[Story],
    tasks: list[QATask],
) -> list[ValidationIssue]:
    story_ids = {story.story_id for story in stories}
    return [
        _issue(
            run_id,
            "task",
            task.task_id,
            ValidationSeverity.S1_CRITICAL,
            "unknown_story",
            "Task references a story_id that Agent B2 did not create.",
            PipelineStage.S5_VALIDATION_B_SYNC,
        )
        for task in tasks
        if task.story_id not in story_ids
    ]


def _missing_story_epic_links(
    run_id: str,
    epics: list[Epic],
    stories: list[Story],
) -> list[ValidationIssue]:
    epic_ids = {epic.epic_id for epic in epics}
    return [
        _issue(
            run_id,
            "story",
            story.story_id,
            ValidationSeverity.S1_CRITICAL,
            "unknown_epic",
            "Story references an epic_id that Agent B1 did not create.",
            PipelineStage.S5_VALIDATION_B_SYNC,
        )
        for story in stories
        if story.epic_id not in epic_ids
    ]


def _apply_routing_status(item: Feature | QATask | TestCase, lane: str) -> None:
    if lane == "AUTO":
        item.review_status = ReviewStatus.AUTO_APPROVED
    elif lane == "BATCH":
        item.review_status = ReviewStatus.NEEDS_REVIEW
    else:
        item.review_status = ReviewStatus.BLOCKED


def _issue(
    run_id: str,
    target_type: str,
    target_id: str,
    severity: ValidationSeverity,
    code: str,
    message: str,
    stage: PipelineStage,
) -> ValidationIssue:
    return ValidationIssue(
        run_id=run_id,
        target_type=target_type,
        target_id=target_id,
        severity=severity,
        code=code,
        message=message,
        stage=stage,
    )
