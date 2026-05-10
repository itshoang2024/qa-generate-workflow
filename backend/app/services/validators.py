from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher

from app.domain.models import (
    Feature,
    GDDSection,
    PipelineStage,
    QATask,
    TestCase,
    TestCategory,
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
