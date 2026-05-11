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
| S4.1 Agent B1 Epic Planner (Phase 1.8) | Single structured-output call sinh epic skeleton: `epic_id`, `title`, `description`, `feature_ids`, `rationale`, `external_id`. No stories or tasks. | `epics` |
| Sync-A1 | Idempotent Notion upsert of epics keyed on `external_id`. Returns `epic_page_id` mapping. | epic SyncEvent[] |
| HIL-1 epic edit (optional, soft gate) | Lead's `<EpicReviewPanel>` may rename epics, drag features, merge two epics, or split one. Triggered between S4.1 and S4.2; auto-passes when Lead clicks `Continue to Stories` without edits. | mutated epic state |
| S4.2 Agent B2 Story Planner (Phase 1.8) | Fan-out per epic. Each fan-out is one `AgentBJob{scope=epic}` with bounded concurrency (default 3). Per call: structured-output produces stories for that epic with `acceptance_criteria`. | stories per epic |
| Sync-A2 | Per-epic Notion upsert of stories keyed on `external_id`. Returns `story_page_id` mapping. | story SyncEvent[] (per epic) |
| S4.3 Agent B3 Task Planner (Phase 1.8) | Fan-out per story. Each fan-out is one `AgentBJob{scope=story}` with bounded concurrency (default 5). Per call: structured-output produces tasks for that story with assignee (rule-lookup), priority, estimate, source_sections, external_id, confidence. | tasks per story |
| S5 Validation B + Router B + HIL-2 | Phase 1.8 splits validators: V-B1 (post S4.1, feature coverage), V-B2 (post each S4.2 fan-out, story coverage per epic), V-B3 (post S4.3, full plan: schema, traceability, mandatory cross-story / cross-epic dedup, assignee sanity, count guardrails). | approved/blocked task sets |
| Sync-B | Task upsert keyed on `external_id` after HIL-2 / Router B auto-approval. | task SyncEvent[] |
| S6 Agent C | Per-approved-task test case generation; does not wait for every task. | test cases |
| S7 Validation C + HIL-3 | Schema, traceability, category coverage, repeatability, and assignee review. | approved/blocked test cases |
| Sync-C | Test case sync after HIL-3 or auto. | test-case sync events |
| Final | Coverage, risk dashboard, Slack/email notification, QA Lead sign-off. | report and sign-off state |

Legacy `S4_AGENT_B` and bundled Sync-A (epics+stories together) remain in the pipeline service for `/demo-runs` smoke-test compatibility. Real provider work and stepped UI use S4.1/S4.2/S4.3 and Sync-A1/Sync-A2 instead.

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
| `S3_VALIDATION_A` | `validate_features_with_routing()` | `ValidationIssue[]`, `RiskEvent[]` |
| `S4_AGENT_B` | `MockAgentClient.plan_qa_tasks()` | `Epic[]`, `Story[]`, `QATask[]`, `AgentRun` |
| `S5_VALIDATION_B_SYNC` | `validate_tasks_with_routing()`, Sync-A, Sync-B | task validation issues, risk events, mock epic/story/task `SyncEvent[]` with phase labels |
| `S6_AGENT_C` | `MockAgentClient.generate_test_cases()` | `TestCase[]`, `AgentRun` |
| `S7_VALIDATION_C_SYNC` | `validate_test_cases_with_routing()`, Sync-C | test-case validation issues, risk events, test-case `SyncEvent[]`, task status transition |
| `FINAL_COVERAGE` | `_coverage_report()` | `Run.coverage_report`, risk/sync/sign-off summaries, completed status |

Each stage appends a `StageEvent` to `Run.timeline`.

## Artifact Ownership

| Artifact | Model | Created by | Stored by |
|---|---|---|---|
| Parsed GDD section | `GDDSection` | parser | `add_sections()` |
| Feature | `Feature` | mock Agent A | `set_features()` |
| Epic | `Epic` | mock Agent B (legacy) / Agent B1 (Phase 1.8) | `set_epics()` |
| Story | `Story` | mock Agent B (legacy) / Agent B2 fan-out per epic (Phase 1.8) | `set_stories()` (Phase 1.8: incremental per epic) |
| QA task | `QATask` | mock Agent B (legacy) / Agent B3 fan-out per story (Phase 1.8) | `set_tasks()` (Phase 1.8: incremental per story) |
| Agent B job (Phase 1.8) | `AgentBJob` | pipeline fan-out orchestrator | `add_agent_b_jobs()` / `update_agent_b_job()` |
| Test case | `TestCase` | mock Agent C | `set_test_cases()` |
| Validation issue | `ValidationIssue` | validators | `add_validation_issues()` |
| Risk event | `RiskEvent` | risk event mapper | `add_risk_events()` |
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
| `external_id` (epic) | `snake-escape-E-CORE-GAMEPLAY` | stable idempotency key for Sync-A1 |
| `external_id` (story, Phase 1.8) | `snake-escape-E-CORE-GAMEPLAY-S-005` | stable idempotency key for Sync-A2 |
| `external_id` (task) | `snake-escape-F-001-T-01` | stable idempotency key for Sync-B; seq counted per `(project_id, feature_id)`, NOT per story, so S4.3 fan-out retry is collision-safe |
| `external_id` (test case) | `snake-escape-F-001-T-01-TC-01` | derived from task external_id |
| `section_id` | `§2.3`, `§12.8` | parser-derived from GDD headings |
| `agent_b_job.id` (Phase 1.8) | `abjob_<12 hex chars>` | generated per fan-out job |

Changing any stable fixture ID affects tests, sync payloads, frontend expectations, and docs.

## Source Traceability

Features, tasks, and test cases must include `source_sections`.

Validators treat unknown source sections as critical errors:

- `missing_source_section`
- `task_missing_source_section`
- `test_case_missing_source_section`

Current source sections use the `§` prefix. Do not replace it with plain numeric section IDs unless all fixture data, parser tests, validators, docs, and frontend expectations are updated together.

## Validation Semantics

Validation issues are non-blocking in Phase 1. They are recorded for demo visibility, and the run may still complete unless the current-run kill switch trips before Agent C.

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
- risk event logging for all Task 4 failure classes

## Risk Event Semantics

Current deterministic mappings:

| Validation issue code | Risk severity | Meaning |
|---|---|---|
| `missing_source_section` | `S1` | Possible hallucination / broken traceability. |
| `task_missing_source_section` | `S1` | Possible task hallucination / broken traceability. |
| `test_case_missing_source_section` | `S1` | Possible test-case hallucination / broken traceability. |
| `uncovered_actionable_section` | `S2` | Scope drift. |
| `invalid_assignee` | `S2` | Assignee mismatch. |
| `duplicate_task_candidate` | `S2` | Duplicate task candidate (within bundled mode). |

Phase 1.8 additions (target):

| Validation issue code | Risk severity | Meaning |
|---|---|---|
| `missing_b1_feature_coverage` | `S2` | Agent B1 dropped one or more approved features from the epic plan. |
| `extra_b1_feature_coverage` | `S2` | Agent B1 placed a feature in too many epics (>3) without cross-cutting flag. |
| `missing_b2_story_for_feature` | `S2` | Agent B2 did not produce a story for an approved feature in an epic. |
| `b2_story_count_out_of_range` | `S3` | Story count guardrail breach (informational). |
| `duplicate_task_cross_story` | `S2` | Hierarchical-mode dedup: two tasks under different stories share >0.85 similar titles. |
| `duplicate_task_cross_epic` | `S2` | Same as above but across different epics; often signals missed cross-cutting feature. |
| `agent_b_substage_timeout` | `S2` | One or more B2/B3 fan-out jobs timed out. Pipeline does not auto-retry; manual recovery via `/agent-b/jobs/{id}/retry`. |
| `agent_b_partial_fanout_failure` | `S2` | More than threshold (default 30%) of fan-out jobs failed after auto-retry; stage paused awaiting Lead. |

`Run.session_memory.kill_switch` stores current-run counters. When S1 risk count reaches the configured threshold, the pipeline records `kill_switch_tripped`, marks the run `FAILED`, and stops before Agent C.

## Target Notion Sync Semantics

Task 3 is authoritative for real Notion sync:

- Notion is destination only; internal pipeline state is source of truth.
- Upsert by `external_id`, never by title or description.
- **Phase 1.8 sync split:**
  - Sync-A1: Epic upsert after S4.1 + V-B1 pass.
  - Sync-A2: Story upsert per epic, streaming after each S4.2 fan-out job completes + V-B2 pass for that epic.
  - Sync-B: Task upsert after S4.3 + V-B3 + HIL-2 or Router B auto-approval.
  - Sync-C: Test Case upsert after HIL-3 or Router C auto-approval.
- Sync failures do not block downstream pipeline generation, with one exception: Sync-A1 failure blocks S4.2 because story relation requires `epic_page_id`. Replay from pipeline state once Notion is reachable.
- Real sync must support schema preflight, throttling around Notion rate limits, retry, dead-letter queue, replay, and manual-edit conflict detection.
- `payload.sync_phase` field values are now: `Sync-A` (legacy bundled, for `/demo-runs` back-compat), `Sync-A1`, `Sync-A2`, `Sync-B`, `Sync-C`.

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
  "tasks_by_priority": {"P0": 5},
  "risk_summary": {"total": 14, "by_severity": {"S2": 14}, "by_code": {}},
  "sync_summary": {
    "total": 55,
    "by_status": {"SUCCESS": 55},
    "by_phase": {"Sync-A": 10, "Sync-B": 9, "Sync-C": 36}
  },
  "gdd_version_metadata": {
    "gdd_document_id": "gdd_...",
    "source_version_id": "v1",
    "source_metadata": {}
  },
  "sign_off": {
    "signed_off": false,
    "signed_off_by": null,
    "signed_off_at": null
  }
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
| Critical risk threshold reached | Stored as `kill_switch_tripped`; run is marked `FAILED` before Agent C. |
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
