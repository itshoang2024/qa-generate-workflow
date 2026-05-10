# Backend Stage Tasks

This checklist tracks backend work against the source-of-truth solution files. Each task includes a verification step so implementation can proceed stage by stage without relying on hidden assumptions.

Progress rule: when a task in this file is completed, update its checkbox from `[ ]` to `[x]` in the same implementation turn or commit, and keep the `Verify:` line directly below it.

## Status Snapshot (last reviewed 2026-05-10)

| Phase | Done / Total | Status |
|---|---|---|
| S0 Trigger + Mode Detection | 1 / 6 | Plan/tasks aligned; request model + handler not started. |
| S1 Context Loader | 0 / 11 | Parser exists in MVP; `GDDDocument`, HIL-0 API, DELTA diff not started. |
| S2 Agent A | 0 / 4 | Mock works; AgentClient interface not extracted. |
| S3 Validation A + Router A | 0 / 3 | Subset of validators exists; router lanes not exposed. |
| HIL-1 | 0 / 3 | Generic `ReviewDecision` exists; queue endpoints missing. |
| S4 Agent B | 0 / 4 | Mock works; structured-output adapter not started. |
| S5 Validation B + Router B + HIL-2 | 0 / 3 | Subset of validators exists. |
| S5b Notion Sync-A/B | 0 / 4 | Mock sync exists; Sync-A vs Sync-B not separated. |
| S6 Agent C | 0 / 3 | Mock generates 4 cases per task. |
| S7 Validation C + HIL-3 | 0 / 2 | Category coverage validator exists. |
| S7b Notion Sync-C | 0 / 2 | Mock sync exists. |
| Final Coverage / Risk / Sign-Off | 0 / 5 | Coverage subset exists; risk events / kill switch missing. |
| Final Backend Verification | 0 / 6 | Pending after Phase 2. |

## Next Implementation Slice — S0 Split + Project + GDDDocument

The MVP `PipelineService.run_demo()` currently collapses S0 (trigger / mode detect) and S1 (parse / actionability) into one method. That violates the Task 1 boundary "S0 does not parse, hash, version, or persist GDD". Fix this first because it unblocks 8+ downstream tasks (project APIs, GDD version history, HIL-0, DELTA diff, AgentClient ingestion shape, frontend upload screen).

Order within this slice:

1. `Phase S0` task 1 → S0 request model accepting either `project_id` OR `project_name` + `gdd_file` reference.
2. `Phase S0` tasks 2-4 → rule-based mode detection, run + session memory init, response shape `{run_id, project_id, gdd_file, mode}`.
3. `Phase S1` task 1 → load raw GDD handed off by S0 (no inline parse inside S0).
4. `Phase S1` tasks 2-7 → `GDDDocument` model, repo methods (create/get/list/latest/next-version), Supabase `gdd_documents` table, optional description fields, upload runtime config.
5. Add `POST /api/v1/runs/trigger` and the three project endpoints (`POST/GET /api/v1/projects`, `GET /api/v1/projects/{id}`) — these are listed in root `TASKS.md` Phase 1.
6. Refactor `PipelineService` into `_stage_s0_trigger()` and `_stage_s1_context_loader()` so `run_demo()` becomes a thin wrapper that calls both for backward compat.

Do not start `Phase S2`+ until this slice is green: Agent A/B/C real adapters and Sync-A/B/C all consume artifacts that S1 (not S0) is supposed to produce.

## Open Phase 0 Items From Root Plan

Two Phase 0 items in root `TASKS.md` are still open and orthogonal to the S0/S1 slice:

- Normalize default GDD path so a clean shell can `POST /api/v1/demo-runs` without setting `SNAKE_GDD_PATH`.
- Decide `.env` handling — currently `config.py` does not auto-load `.env`; `/api/v1/health` should reflect the active providers explicitly.

These can be picked up in parallel since they touch only `config.py`, `health` endpoint, and runbooks.

## Phase S0 - Trigger + Mode Detection

- [x] Task: Revise backend plan/tasks so S0 only owns trigger, mode detection, run creation, and session initialization.
  Verify: `rg -n "S0 does not|Input: GDD upload|mode=DELTA|mode=NEW_GAME|session memory" backend/PLAN.md backend/TASKS.md`.

- [ ] Task: Add S0 request model for GDD upload reference plus project selection.
  Verify: Request can represent either existing `project_id` or new project name, plus `gdd_file`.

- [ ] Task: Implement rule-based mode detection.
  Verify: Existing project selection produces `mode=DELTA`; new project creation produces `mode=NEW_GAME`.

- [ ] Task: Create run ID and initialize session memory.
  Verify: S0 response includes `{run_id, project_id, gdd_file, mode}` and session memory exists for the run.

- [ ] Task: Keep S0 free of parser/storage/versioning side effects.
  Verify: S0 test asserts no GDD sections and no `GDDDocument` record are created before S1.

- [ ] Task: Preserve `/api/v1/demo-runs`.
  Verify: Existing demo run API still creates a completed Snake Escape run with a complete timeline in mock mode.

## Phase S1 - Context Loader

- [ ] Task: Load raw GDD file handed off by S0.
  Verify: S1 receives `gdd_file`, reads the file, and reports a clear error for missing files.

- [ ] Task: Add `GDDDocument` domain model.
  Verify: Model includes `project_id`, `version_id`, optional `description`, `description_status`, `parent_document_id`, file metadata, and `sha256`.

- [ ] Task: Extend `Run` with GDD document and source version metadata after S1 registration.
  Verify: Run detail includes `gdd_document_id`, `source_version_id`, and source metadata after S1 completes.

- [ ] Task: Add repository methods for project get/list.
  Verify: Memory and Supabase repositories can create, fetch, and list projects.

- [ ] Task: Add repository methods for GDD document create/get/list/latest/next version.
  Verify: Tests show the first document for a project is `v1` and the second is `v2`.

- [ ] Task: Add Supabase `gdd_documents` schema.
  Verify: `supabase/schema.sql` creates `gdd_documents`, unique `(project_id, version_id)`, and indexes for project/document lookup.

- [ ] Task: Add upload/runtime storage settings.
  Verify: Config exposes `UPLOAD_DIR` and `MAX_UPLOAD_BYTES`, uploaded files go under `backend/.runtime/uploads/`, and runtime uploads are git-ignored.

- [ ] Task: Add `python-multipart` for FastAPI upload handling when route implementation needs multipart.
  Verify: `pip install -r backend/requirements.txt` installs upload dependencies in `qa-generator`.

- [ ] Task: Add S1 structural DOCX parse.
  Verify: Parser tests assert headings, tables, special blocks, and stable section order.

- [ ] Task: Add QA-actionability filter.
  Verify: Tests show metadata/external-dependency sections are excluded and behavior/UI/data sections are actionable.

- [ ] Task: Add HIL-0 preflight issue model/API.
  Verify: API tests can list one batch of clarification questions and resolve with provide-artifact, proceed-with-flag, or skip.

- [ ] Task: Add S1.4 DELTA diff scaffold.
  Verify: DELTA mode loads previous GDD version and emits `NEW`, `MODIFIED`, `UNCHANGED`, `REMOVED` buckets or a placeholder with stable shape.

## Phase S2 - Agent A

- [ ] Task: Introduce a shared `AgentClient` interface for agent calls.
  Verify: Mock Agent A uses the interface without changing current demo output.

- [ ] Task: Implement Task 2 Agent A structured JSON contract.
  Verify: Output contains `features`, `coverage_report`, `ambiguities`, source sections, confidence, and optional DELTA status.

- [ ] Task: Keep fixture-backed mock Agent A as the default provider.
  Verify: Tests pass with no AI credentials configured.

- [ ] Task: Add real AI provider selection behind `AI_PROVIDER`.
  Verify: Setting an unsupported provider returns a clear startup or request error.

## Phase S3 - Validation A + Router A

- [ ] Task: Validate Agent A schema, source traceability, keyword overlap, coverage, and confidence.
  Verify: Unit tests cover schema failure, missing source, hallucination suspect, uncovered section, and low confidence.

- [ ] Task: Add Router A lanes.
  Verify: `>=0.85` auto-proceeds, `[0.6,0.85)` goes to HIL-1, and `<0.6` blocks.

- [ ] Task: Add retry/rerun behavior for schema, traceability, and uncovered-section failures.
  Verify: Tests show bounded retry and stable escalation after max attempts.

## Phase HIL-1 - Epic-Level Review

- [ ] Task: Extend review decisions for feature and epic targets.
  Verify: `POST /api/v1/review-decisions` accepts feature/epic target types and rejects unknown targets.

- [ ] Task: Store approved feature list and epic structure in session memory.
  Verify: Agent B consumes approved/corrected HIL-1 output, not raw Agent A output.

- [ ] Task: Add review listing endpoints if required by frontend queues.
  Verify: Frontend can query pending feature/epic review items without scanning every artifact manually.

## Phase S4 - Agent B

- [ ] Task: Move Agent B behind the shared `AgentClient` interface.
  Verify: Demo run still creates deterministic epics, stories, and tasks.

- [ ] Task: Implement Task 2 Agent B structured JSON contract.
  Verify: Output uses Epic -> Story -> Task tree with `feature_id`, `source_sections`, `external_id`, priority justification, estimate, and confidence.

- [ ] Task: Enforce rule-based assignee mapping.
  Verify: Agent output cannot freelance an assignee outside KB mapping.

- [ ] Task: Add DELTA task behavior.
  Verify: Unchanged features skip, modified features create update/retest tasks, new features create tasks, and removed features create archive tasks.

## Phase S5 - Validation B + Router B + HIL-2

- [ ] Task: Validate schema, traceability, cross-agent references, dedup, assignee sanity, confidence, and task count guardrails.
  Verify: Unit tests cover each validation issue code.

- [ ] Task: Add Router B lanes.
  Verify: Auto, Batch, and Block lanes follow Task 1 confidence and dedup/cross-cutting rules.

- [ ] Task: Add HIL-2 decisions for task approval, edit request, rejection, and assignee override.
  Verify: API tests show review decisions change task review state without deleting original agent output.

## Phase S5b - Notion Sync-A/B

- [ ] Task: Introduce a `NotionSyncClient` interface with mock and real providers.
  Verify: Mock sync still records payloads in `sync_events`.

- [ ] Task: Implement Sync-A for Epic and Story after HIL-1.
  Verify: Epic/Story sync records page-id mappings before task sync starts.

- [ ] Task: Implement Sync-B for Task after HIL-2 or Router B auto-approval.
  Verify: Task upsert uses `external_id`, relation page IDs, confidence behavior, and DELTA status.

- [ ] Task: Add Notion schema validation, throttling, retry, replay, and dead-letter behavior.
  Verify: Missing properties block sync; 429 retries; failed events are replayable.

## Phase S6 - Agent C

- [ ] Task: Move Agent C behind the shared `AgentClient` interface.
  Verify: Demo run still creates deterministic test cases from the fixture.

- [ ] Task: Implement Task 2 Agent C structured JSON contract.
  Verify: Each approved task receives positive, negative, edge, and integration coverage where applicable.

- [ ] Task: Enforce concrete test data and repeatability rules.
  Verify: Vague phrases and RNG without seed create validation issues.

## Phase S7 - Validation C + HIL-3

- [ ] Task: Validate schema, source traceability, category coverage, one-assertion expected result, forbidden vague phrases, repeatability, and task links.
  Verify: Unit tests cover each issue code.

- [ ] Task: Add HIL-3 decisions for test case approval, edit request, and rejection.
  Verify: API tests show assignees can review their own generated test cases.

## Phase S7b - Notion Sync-C

- [ ] Task: Implement Sync-C for test cases after HIL-3 or Router C auto-approval.
  Verify: Test cases link to task pages by page ID resolved from `external_id`.

- [ ] Task: Update task status to `Test Cases Ready` when test cases are approved and synced.
  Verify: Sync event and task status reflect the transition.

## Phase Final - Coverage, Risk, And Sign-Off

- [ ] Task: Expand coverage/report API for frontend summary screens.
  Verify: API response includes section coverage, story coverage, assignee distribution, priority distribution, validation summary, sync summary, risk metrics, GDD version metadata, and sign-off state.

- [ ] Task: Add risk event model and dashboard data.
  Verify: Simulated scope drift, hallucination, duplicate, bad assignee, sync failure, and missing info produce stored risk events.

- [ ] Task: Add learning-loop correction records.
  Verify: HIL corrections can be stored and retrieved for future prompt context.

- [ ] Task: Add kill-switch behavior.
  Verify: High hallucination/rejection/sync-error thresholds stop or pause the correct subsystem and log state for recovery.

- [ ] Task: Add reviewer sign-off model and endpoint.
  Verify: API tests can record sign-off and show it in the final report.

## Final Backend Verification

- [ ] Task: Run the backend test suite.
  Verify: `conda run -n qa-generator python -m pytest` passes from `backend/`.

- [ ] Task: Run backend linting.
  Verify: `conda run -n qa-generator python -m ruff check .` passes from `backend/`.

- [ ] Task: Run manual Swagger demo.
  Verify: `POST /api/v1/demo-runs` creates a run, and timeline, coverage, tasks, test cases, validation issues, and sync payloads are inspectable.

- [ ] Task: Run source-of-truth Stage 0/Stage 1 Swagger demo after implementation.
  Verify: Upload + new project creates `NEW_GAME`; upload + existing project creates `DELTA`; S1 registers/parses GDD and emits HIL-0/DELTA context.

- [ ] Task: Run Notion smoke test when credentials are configured.
  Verify: Sync-A/B/C upsert records by `external_id`, preserve page-id relations, and replay failed events without duplicates.

- [ ] Task: Confirm mock fallback remains stable.
  Verify: Removing AI, Notion, and Supabase credentials still allows the complete demo run to finish.
