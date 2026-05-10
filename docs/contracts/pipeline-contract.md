# Pipeline Contract

## Purpose

This document defines the current Phase 1 demo pipeline contract. It is the source of truth for stage order, generated artifacts, ID conventions, validation semantics, and compatibility risks.

Implementation entry point: `backend/app/services/pipeline.py`.

## Supported Invocation

The only supported Phase 1 pipeline request is:

```json
{
  "preset": "snake_escape",
  "mode": "NEW_GAME",
  "auto_approve": true
}
```

`mode="DELTA"` is accepted by the model but does not activate a delta implementation. `auto_approve` is accepted but currently does not alter pipeline branching.

## Stage Order

| Stage | Implementation | Main outputs |
|---|---|---|
| `S0_TRIGGER` | `PipelineService.run_demo()` | `Project`, `Run` |
| `S1_CONTEXT_LOADER` | `parse_docx_gdd()` | `GDDSection[]` |
| `S2_AGENT_A` | `MockAgentClient.analyze_gdd()` | `Feature[]`, `AgentRun` |
| `S3_VALIDATION_A` | `validate_features()` | `ValidationIssue[]` |
| `S4_AGENT_B` | `MockAgentClient.plan_qa_tasks()` | `Epic[]`, `Story[]`, `QATask[]`, `AgentRun` |
| `S5_VALIDATION_B_SYNC` | `validate_tasks()`, `MockNotionSyncClient` | task validation issues, epic/story/task `SyncEvent[]` |
| `S6_AGENT_C` | `MockAgentClient.generate_test_cases()` | `TestCase[]`, `AgentRun` |
| `S7_VALIDATION_C_SYNC` | `validate_test_cases()`, `MockNotionSyncClient` | test-case validation issues, test-case `SyncEvent[]` |
| `FINAL_COVERAGE` | `_coverage_report()` | `Run.coverage_report`, completed status |

Each stage appends a `StageEvent` to `Run.timeline`.

## Artifact Ownership

| Artifact | Model | Created by | Stored by |
|---|---|---|---|
| Parsed GDD section | `GDDSection` | parser | `add_sections()` |
| Feature | `Feature` | mock Agent A | `set_features()` |
| Epic | `Epic` | mock Agent B | `set_epics()` |
| Story | `Story` | mock Agent B | `set_stories()` |
| QA task | `QATask` | mock Agent B | `set_tasks()` |
| Test case | `TestCase` | mock Agent C | `set_test_cases()` |
| Validation issue | `ValidationIssue` | validators | `add_validation_issues()` |
| Agent snapshot | `AgentRun` | pipeline | `add_agent_run()` |
| Mock Notion sync | `SyncEvent` | mock Notion adapter | `add_sync_events()` |

## ID Conventions

| Field | Pattern in current demo | Stability |
|---|---|---|
| `run.id` | `run_<12 hex chars>` | generated per run |
| `feature_id` | `F-001`, `F-002` | stable within fixture |
| `epic_id` | `E-CORE-GAMEPLAY` | stable within fixture |
| `story_id` | `S-001` | stable within fixture |
| `task_id` | `T-001` | stable within fixture |
| `test_case_id` | `TC-0001` | generated per run from tasks |
| `external_id` | `snake-escape-F-001-T-01` or task-derived TC ID | stable idempotency key |
| `section_id` | `§2.3`, `§12.8` | parser-derived from GDD headings |

Changing any stable fixture ID affects tests, sync payloads, frontend expectations, and docs.

## Source Traceability

Features, tasks, and test cases must include `source_sections`.

Validators treat unknown source sections as critical errors:

- `missing_source_section`
- `task_missing_source_section`
- `test_case_missing_source_section`

Current source sections use the `§` prefix. Do not replace it with plain numeric section IDs unless all fixture data, parser tests, validators, docs, and frontend expectations are updated together.

## Validation Semantics

Validation issues are non-blocking in Phase 1. They are recorded for demo visibility, and the run may still complete.

| Severity | Meaning |
|---|---|
| `S1_CRITICAL` | Silent-breakage risk, such as unknown source IDs or invalid assignees. |
| `S2_RECOVERABLE` | Needs human review or retry in a future implementation, such as low confidence. |
| `S3_INFORMATIONAL` | Useful signal, such as uncovered sections or GDD notes. |

Current validators:

- Feature validation: source references, low confidence, uncovered actionable sections, pre-flight notes.
- Task validation: feature references, assignees, source references, low confidence, duplicate candidate titles.
- Test-case validation: related task references, source references, four-category coverage.

## Coverage Report Shape

`Run.coverage_report` currently includes:

```json
{
  "total_sections": 55,
  "actionable_sections": 41,
  "covered_sections": ["§2.3"],
  "uncovered_sections": ["§8.3"],
  "feature_count": 8,
  "task_count": 11,
  "test_case_count": 44,
  "validation_issue_count": 21,
  "tasks_by_assignee": {"Ngoc Anh": 2},
  "tasks_by_priority": {"P0": 5}
}
```

Counts are demo expectations, not universal constants.

## Failure Modes

| Failure | Current behavior |
|---|---|
| Unsupported preset | `ValueError`, returned as HTTP 422 by API route. |
| Missing GDD path | `FileNotFoundError`, returned as HTTP 404 by API route. |
| Unexpected pipeline exception | Run is marked `FAILED`, then exception is raised. |
| Validation issue | Stored and surfaced by `/validation-issues`; pipeline continues. |
| Mock sync failure | Not currently simulated except by manually storing failed `SyncEvent` records. |

## Validation Checklist For Pipeline Changes

Run:

```powershell
cd D:\Code\SUNS-RISER\qa-generate-workflow
conda activate qa-generator
cd backend
pytest
python -m ruff check .
```

Also update this doc when changing:

- stage names or order
- artifact ownership
- ID formats
- validation issue codes
- coverage report shape
- whether validation blocks the run

