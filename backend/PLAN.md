# Backend Completion Plan

## Goal

Complete the backend according to the four source-of-truth solution files in the workspace root:

- `Task-1-AI-workflow-design.md`
- `Task-2-Agent-prompts-JSON.md`
- `Task-3-Sync-to-Notion.md`
- `Task-4-Risk-Failure-handling.md`

The backend must remain mock-first for the local demo while evolving toward the full staged workflow: S0 trigger/mode detection, S1 rule-based context loading, Agent A/B/C structured JSON output, validation routers, HIL gates, Notion Sync-A/B/C, risk handling, and final coverage/sign-off.

## Current Backend State (2026-05-11)

- FastAPI app, versioned routes, domain models, repository abstraction (in-memory + Supabase), Snake Escape fixture, Supabase schema, runbooks, and backend tests are in place.
- `POST /api/v1/demo-runs` runs the seeded Snake Escape flow and produces sections, features, epics, stories, tasks, test cases, validation issues, risk events, agent runs, Sync-A/B/C events, coverage, sign-off state, and timeline. Demo counts remain 8 features / 5 epics / 5 stories / 11 tasks / 44 test cases in mock mode.
- `_stage_s0_trigger` and `_stage_s1_context_loader` are split. S0 only creates a run + initializes `session_memory`; S1 owns raw load, `GDDDocument` versioning (`v1`, `v2`, ...), structural parse, QA-actionability filter, HIL-0 question batching, and DELTA section diff (`NEW`/`MODIFIED`/`UNCHANGED`/`REMOVED`).
- `AgentClient` abstract base is implemented with `MockAgentClient` as the default. Agent A now has a Task 2 structured JSON contract, optional `delta_status`, an OpenAI Responses API adapter behind `AI_PROVIDER=openai`/`real`, and mock-backed Agent B/C fallback until their real contracts ship.
- S3 Validation A now retries Agent A schema failures, source traceability failures, and uncovered-section reruns up to 3 attempts. Attempt logs are stored in the AgentRun output snapshot and `Run.session_memory`; exhausted retries emit `agent_a_retry_exhausted` and route the final output to HIL-1 instead of silently proceeding.
- Router lanes ship end-to-end: `derive_router_lane` thresholds in `domain/models.py`, applied by `validate_*_with_routing`, exposed as computed `Feature.lane` / `QATask.lane` / `TestCase.lane`, and surfaced via `GET /api/v1/runs/{run_id}/review-queues/{HIL-tier}`. `ReviewDecision` cascades epic -> features + stories.
- `NotionSyncClient` abstract base and `MockNotionSyncClient` are implemented. Sync-A writes epics/stories, Sync-B writes eligible tasks with mock page-id relations, and Sync-C writes eligible test cases and transitions synced parent tasks to `Test Cases Ready`.
- Risk events, kill switch, reviewer sign-off, and the extended coverage report (`risk_summary`, `sync_summary`, `gdd_version_metadata`, `sign_off`) are implemented. Learning-loop correction memory is still open.
- Frontend is not scaffolded.

## Stage-Based Plan

### S0 Trigger + Mode Detection

S0 is rule-based and intentionally small.

Source-of-truth behavior:

- Input: GDD upload plus project selection.
- If the user selects an existing project from the dropdown, set `mode=DELTA`.
- If the user creates a new project, set `mode=NEW_GAME`.
- Create a new `run_id`.
- Initialize session memory.
- Output `{run_id, project_id, gdd_file, mode}`.

S0 must not:

- parse the GDD
- hash the file
- persist detailed GDD document metadata
- generate `version_id`
- run DELTA diff
- call AI
- sync to Notion

Those responsibilities start in S1 or later.

Backend outputs:

- `Run`
- `project_id`
- uploaded/raw `gdd_file` reference
- `mode`
- initialized session memory pointer/record
- `StageEvent` for S0

Acceptance:

- New project selection creates a run with `mode=NEW_GAME`.
- Existing project selection creates a run with `mode=DELTA`.
- Response includes `{run_id, project_id, gdd_file, mode}` inside the API envelope.
- `/demo-runs` remains backward-compatible for the mock Snake Escape demo.

### S1 Context Loader

S1 is rule-based and owns GDD raw loading, versioning, structural context, HIL-0, and DELTA diff.

#### S1.1 Structural Parse

Target behavior:

- Load the raw GDD file handed off by S0.
- Register a `GDDDocument` knowledge-base record for the project.
- Auto-generate `version_id` per project as `v1`, `v2`, `v3`, and so on.
- Store optional `description`, `description_status`, `parent_document_id`, filename/path metadata, origin, size, content type, and `sha256`.
- Parse markdown/docx structure: section hierarchy, heading levels, tables, and IMPORTANT/NOTE/TIP blocks.
- Extract game overview fields by fixed template.
- Output `gdd_tree` with `section_id`, `parent_id`, `text`, `tables`, and `flags`.

Acceptance:

- Uploading the first GDD for a project creates `version_id=v1`.
- Uploading the second GDD for the same project creates `version_id=v2`.
- Parser tests prove headings, tables, special blocks, and stable section order are extracted.

#### S1.2 QA-Actionability Filter

Target behavior:

- Mark each section as QA-actionable using deterministic heuristics.
- External-reference-only sections become `actionable=false, reason=external_dep`.
- Metadata sections such as Game Overview and Scope Summary become `actionable=false, reason=metadata`.
- Behavior/UI/data sections become `actionable=true`.
- Non-actionable sections are flagged and excluded from main agent analysis.

Acceptance:

- Feature generation receives only traceable, relevant context.
- Non-actionable content does not create noisy QA tasks.

#### S1.3 HIL-0 Preflight Clarification

Target behavior:

- Detect missing artifacts from IMPORTANT/NOTE/TIP blocks.
- Detect ambiguous thin sections and dangling references.
- Batch all clarification questions into one review screen.
- Support user choices: provide artifact, proceed-with-flag, or skip section.

Acceptance:

- Frontend can show one HIL-0 question batch before Agent A.
- Proceed-with-flag caps confidence and marks incomplete source.
- Skipped sections appear in final coverage.

#### S1.4 DELTA Diff

Target behavior:

- Run only when S0 set `mode=DELTA`.
- Load previous GDD version from long-term memory.
- Compare sections as `NEW`, `MODIFIED`, `UNCHANGED`, or `REMOVED`.
- Load existing Notion tasks for the game.
- Output `delta_report`.

Acceptance:

- Later Agent A/B inputs include `delta_report`.
- `GDDDocument.parent_document_id` links the current version to the compared prior version.

### S2 Agent A - GDD Analyzer

Target behavior from Task 2:

- Input: `actionable_sections`, `user_clarifications`, and `delta_report` when DELTA.
- Output strict JSON with `features`, `coverage_report`, and `ambiguities`.
- Every feature must cite `source_sections`.
- Feature types include gameplay, UI, level, economy, backend/liveops, animation, tutorial, and cross-cutting.
- Agent uses low temperature and structured output where provider supports it.

Acceptance:

- Mock output remains stable.
- Real output validates against schema before persistence.
- Hallucinated or weakly grounded output never bypasses validation.

### S3 Validation A + Router A

Target behavior:

- Validate schema, source traceability, keyword overlap, coverage, and confidence.
- Retry schema/traceability failures up to policy limits.
- Re-run Agent A for uncovered sections when useful.
- Route by final confidence:
  - `>=0.85` auto-proceed
  - `[0.6, 0.85)` HIL-1 batch
  - `<0.6` block/HIL-1

Acceptance:

- Validation issues include stable codes and severity.
- Router lanes are visible to frontend.

### HIL-1 Epic-Level Review

Target behavior:

- QA Lead reviews feature inventory, epic candidates, coverage map, low-confidence items, and split/merge suggestions.
- Lead can approve all, edit item, change assignee, merge/split epic, skip due to insufficient info, or request Agent A rerun with feedback.
- Approved feature list and epic structure are saved to short-term memory.

Acceptance:

- Agent B consumes only approved/corrected features and epic structure.

### S4 Agent B - QA Planner

Target behavior from Task 2:

- Input: approved features, epic grouping, and per-game memory.
- Output Epic -> Story -> Task tree.
- Assignee is rule-based from KB mapping, not invented by AI.
- `external_id` uses stable project/feature/task pattern.
- DELTA behavior:
  - unchanged features skip
  - modified features create update/retest tasks linked by external_id
  - new features create new tasks
  - removed features create archive tasks for Lead confirmation

Acceptance:

- Task output validates against JSON schema and Pydantic models.
- Invalid assignees and duplicate tasks are caught before sync.

### S5 Validation B + Router B + HIL-2

Target behavior:

- Validate schema, traceability, cross-agent feature references, dedup, assignee sanity, confidence, and task count guardrails.
- Router B lanes:
  - Auto: confidence `>=0.85`, no cross-cutting flag, no dedup flag
  - Batch: confidence `[0.65, 0.85)`
  - Block: confidence `<0.65` or dedup/cross-cutting flag
- HIL-2 provides batch review screens grouped by assignee and feature/epic.

Acceptance:

- Only approved or auto-approved tasks are eligible for task sync and Agent C.

### S5b Notion Sync

Task 3 refines sync into three sub-events. Backend may keep S5b/S7b stage labels, but implementation must distinguish:

- Sync-A: Epic + Story after HIL-1.
- Sync-B: Task after HIL-2 or Router B auto-approval.
- Sync-C: Test Case after HIL-3 or Router C auto-approval.

Target behavior:

- Notion is destination only; pipeline state is source of truth.
- Upsert by `external_id`, never title/description.
- Sync failure does not block downstream pipeline work.
- Retry with backoff; use dead-letter queue after max retries.
- Maintain external_id -> Notion page_id mapping for relations.

Acceptance:

- Sync events preserve payload, action, status, retry count, and error.
- Replay can resume from pipeline state without duplicates.

### S6 Agent C - Test Case Generator

Target behavior from Task 2:

- Trigger per approved task, without waiting for all tasks to be approved.
- Input: one approved task, feature context, and source section text.
- Output test cases covering positive, negative, edge, and integration categories.
- One assertion per expected result.
- Concrete preconditions/test_data; RNG-dependent tests require seed or non-deterministic marker.

Acceptance:

- Each eligible task has required category coverage or explicit `[GAP]` placeholder.
- Test cases inherit task priority and source sections.

### S7 Validation C + HIL-3

Target behavior:

- Validate schema, source traceability, four-category coverage, repeatability, forbidden vague phrases, one-assertion expected result, and related task links.
- Assignees review their own test cases in HIL-3.
- Lead review is not required for every test case unless risk rules trigger it.

Acceptance:

- Invalid or incomplete-source test cases cannot auto-sync.

### S7b Test Case Sync

Target behavior:

- Sync-C appends or upserts test cases in Notion.
- Link test cases to task pages by Notion page_id resolved from `external_id`.
- Update task status from `Ready for Test Cases` to `Test Cases Ready` when appropriate.

Acceptance:

- Test case sync is idempotent and replayable.

### Final Coverage Report + Sign-off

Target behavior:

- Report section coverage, story coverage, assignee distribution, P0/P1/P2 ratio, validation issues, sync status, risk metrics, and sign-off.
- Notify QA Lead via email/Slack with report and Notion links.
- Lead sign-off completes the workflow.

Acceptance:

- One run can show traceability from GDD version to section, feature, task, test case, validation issue, sync event, risk event, and sign-off.

## Cross-Cutting Backend Requirements

- All successful public API responses keep `{ data, meta, error }`.
- Mock providers remain the default for local demo and tests.
- Supabase persistence remains optional until explicitly configured.
- Real agents must use structured JSON output and schema validation.
- Validation and risk handling must use stable issue/event codes.
- Session memory is per-run; long-term memory is per-project.
- Every auto-decision logs a reason.
- Stage boundaries from Task 1 are authoritative.

## Backend Acceptance Criteria

- `pytest` passes in `backend/`.
- `python -m ruff check .` passes in `backend/`.
- Swagger can still run `/api/v1/demo-runs`.
- Target Stage 0 can create a run from upload + project selection without parsing the file.
- Target S1 can register/version/parse the uploaded GDD and produce HIL-0/DELTA context.
