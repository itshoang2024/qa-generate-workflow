# Pipeline Contract

## Purpose

This document defines the current Phase 1 demo pipeline contract and the target stage contract derived from the root source-of-truth solution files:

- `Task-1-AI-workflow-design.md`
- `Task-2-Agent-prompts-JSON.md`
- `Task-3-Sync-to-Notion.md`
- `Task-4-Risk-Failure-handling.md`

When this document conflicts with those four files, revise this document. The current MVP section describes implemented code; the target section describes what the backend should evolve toward.

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

## Target Stage Ownership

| Stage | Source-of-truth responsibility | Key output |
|---|---|---|
| S0 Trigger + Mode Detection | Rule-based split from GDD upload + project selection. Existing project -> `DELTA`; new project -> `NEW_GAME`; create `run_id`; initialize session memory. S0 does not parse, hash, version, or persist detailed GDD metadata. | `{run_id, project_id, gdd_file, mode}` |
| S1 Context Loader | Rule-based raw GDD loading, GDD document version registration, structural parse, QA-actionability filter, HIL-0 questions, and DELTA diff. | `gdd_tree`, `actionable_sections`, `user_clarifications`, optional `delta_report` |
| S2 Agent A | Structured-output GDD Analyzer producing feature inventory. | `features`, `coverage_report`, `ambiguities` |
| S3 Validation A + Router A | Schema, traceability, keyword-overlap, coverage, confidence validation. | validation issues, auto/HIL/block lanes |
| HIL-1 | QA Lead approves/corrects features and epic grouping. | approved feature list and epic structure |
| S4 Agent B | Structured-output QA Planner producing Epic -> Story -> Task tree. | epics, stories, tasks |
| S5 Validation B + Router B + HIL-2 | Cross-agent checks, dedup, assignee sanity, confidence lanes, task review. | approved/blocked task sets |
| S5b / Sync-A/B | Task 3 refines Notion sync into Sync-A (Epic/Story after HIL-1) and Sync-B (Task after HIL-2 or auto). | sync events, page-id mappings |
| S6 Agent C | Per-approved-task test case generation; does not wait for every task. | test cases |
| S7 Validation C + HIL-3 | Schema, traceability, category coverage, repeatability, and assignee review. | approved/blocked test cases |
| S7b / Sync-C | Test case sync after HIL-3 or auto. | test-case sync events |
| Final | Coverage, risk dashboard, Slack/email notification, QA Lead sign-off. | report and sign-off state |

## Target Rule-Based Vs AI Boundary

- Rule-based: S0 mode detection, S1 structural parsing, S1 actionability filter, S1 DELTA diff scaffold, assignee mapping, `external_id` generation, Notion create/update decision, validation, routers, risk detection, retry policy.
- AI: Agent A feature summaries/classification, Agent B story/task narrative and priority/estimate justification, Agent C test case wording and concrete test data.
- Every AI output must be strict JSON or structured output, then schema-validated before persistence.

## Target Risk And Failure Semantics

Task 4 defines the risk model:

| Severity | Default action |
|---|---|
| S1 Critical | Block pipeline or item, escalate Lead, log to long-term memory. |
| S2 Recoverable | Retry/fallback with backoff, then human-in-loop. |
| S3 Informational | Flag and proceed with metadata. |

The target backend should store risk events for scope drift, hallucination, JSON format failure, duplicates, bad assignee, Notion sync failure, and missing GDD information.

## Stage Order

Current MVP implementation:

| Stage | Implementation | Main outputs |
|---|---|---|
| `S0_TRIGGER` | `PipelineService.run_demo()` | `Project`, `Run` |
| `S1_CONTEXT_LOADER` | `parse_docx_gdd()` | `GDDSection[]` |
| `S2_AGENT_A` | `MockAgentClient.analyze_gdd()` | `Feature[]`, `AgentRun` |
| `S3_VALIDATION_A` | `validate_features()` | `ValidationIssue[]` |
| `S4_AGENT_B` | `MockAgentClient.plan_qa_tasks()` | `Epic[]`, `Story[]`, `QATask[]`, `AgentRun` |
| `S5_VALIDATION_B_SYNC` | `validate_tasks()`, `MockNotionSyncClient` | task validation issues, mock epic/story/task `SyncEvent[]` |
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

Target validators additionally include:

- schema validation for every agent output
- keyword overlap / source grounding checks
- cross-agent feature/task/test-case consistency
- hallucination and numerical claim checks
- forbidden vague phrase checks
- retry and escalation policy
- risk event logging

## Target Notion Sync Semantics

Task 3 is authoritative for real Notion sync:

- Notion is destination only; internal pipeline state is source of truth.
- Upsert by `external_id`, never by title or description.
- Sync-A: Epic + Story after HIL-1.
- Sync-B: Task after HIL-2 or Router B auto-approval.
- Sync-C: Test Case after HIL-3 or Router C auto-approval.
- Sync failures do not block downstream pipeline generation.
- Real sync must support schema preflight, throttling around Notion rate limits, retry, dead-letter queue, replay, and manual-edit conflict detection.

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
