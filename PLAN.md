# End-to-End Prototype Completion Plan

## Goal

Complete `qa-generate-workflow` as a credible end-to-end webapp prototype for the SUN.RISER Round 2 homework submission. The source of truth for product behavior is the four root-level solution files:

- `Task-1-AI-workflow-design.md`
- `Task-2-Agent-prompts-JSON.md`
- `Task-3-Sync-to-Notion.md`
- `Task-4-Risk-Failure-handling.md`

The prototype should show how a GDD upload and project selection become a mode-aware QA workflow, then a reviewable execution plan with features, tasks, test cases, validation gates, human review, Notion sync records, risk handling, and a coverage/sign-off report.

Mock mode remains mandatory for a stable local demo. Real AI, real Notion, Supabase persistence, DELTA processing, and LLM-generated GDD version descriptions are target capabilities.

## Current State (last reviewed 2026-05-11 - post stage-flow, bulk HIL-0, and offline font pass)

> **Stage-flow status:** the previous blocker is closed. The backend now exposes per-stage endpoints after S1, the dashboard has a stage-aware CTA, blocking HIL gates are enforced, and the HIL-0 "Proceed with flag" bulk action is one backend request instead of a burst of parallel Supabase writes.

Already implemented:

- FastAPI backend under `backend/` with `{ data, meta, error }` envelope and exception handlers.
- Synchronous Snake Escape demo pipeline through `/api/v1/demo-runs` producing 8 features / 5 epics / 5 stories / 11 tasks / 44 test cases, plus validation issues, risk events, Sync-A/B/C events, coverage, and timeline.
- DOCX parser for the sample GDD with QA-actionability rules (`§13` = `external_dependency`, metadata sections excluded).
- `AgentClient` abstract interface at `app/services/agents/__init__.py` with `MockAgentClient` reading `data/snake_escape_fixture.json`; Agent A also has a Task 2 structured JSON contract and an OpenAI adapter behind `AI_PROVIDER=openai`/`real`.
- Deterministic validators (`validate_features`, `validate_tasks`, `validate_test_cases`) for source traceability, confidence, assignee sanity, duplicate candidates, and test-case category coverage; plus `validate_*_with_routing` wrappers that assign `AUTO` / `BATCH` / `BLOCK` lanes per the Task 1 thresholds.
- S3 Agent A retry/rerun policy: schema failures, source traceability failures, and uncovered-section reruns are bounded to 3 attempts, logged in AgentRun/session memory, and escalated with `agent_a_retry_exhausted` after max attempts.
- HIL-1 session snapshot: approved feature IDs, held/review-queue feature IDs, approved feature details, and deterministic epic candidates are stored in `Run.session_memory["hil_1"]` and passed to Agent B as `hil_context`.
- `NotionSyncClient` abstract interface with mock Sync-A/B/C events, `external_id` idempotency shape, mock page-id relation mapping, and `replay_failed_sync_events` repository hook.
- Router lanes exposed on `Feature`, `QATask`, `TestCase` as computed `lane` fields plus `review_status` on every artifact.
- HIL-0..HIL-3 review queues via `GET /api/v1/runs/{run_id}/review-queues/{tier}` grouped by reviewer / feature / epic; review-decision cascade (approving an epic propagates to its features and stories).
- Project APIs (`POST/GET /api/v1/projects`, `GET /api/v1/projects/{id}`), S0 trigger (`POST /api/v1/runs/trigger`), S1 context (`POST /api/v1/runs/{run_id}/context`), GDD version history (`GET /api/v1/projects/{project_id}/gdd-documents`), HIL-0 questions/resolutions APIs including bulk resolution, and DELTA diff with `NEW`/`MODIFIED`/`UNCHANGED`/`REMOVED` buckets.
- Provider readiness endpoint `GET /api/v1/providers/status` reporting AI / Notion / repository credential state.
- In-memory repository by default and optional Supabase repository, with full parity across projects, runs, GDD documents, sections, HIL-0 questions/resolutions, agent runs, review decisions, and sync events.
- Risk event model/API, kill switch, reviewer sign-off endpoint, and coverage report extensions for `risk_summary`, `sync_summary`, `gdd_version_metadata`, and `sign_off`.
- Supabase schema in `supabase/schema.sql` including `runs` upgrades for `session_memory`, `gdd_document_id`, `source_version_id`, `source_metadata`, `delta_report`, and generated artifact/risk/sync tables.
- Backend tests (parser, validators, pipeline, agents, API, config, supabase schema) covering the demo counts, S0 split, S1 versioning + DELTA, HIL queues, and review-decision lane updates.
- Docs, contracts, runbooks, fixture guide, and planning docs.

Shipped in the Phase 1.5 / F3.5 pass:

- **Per-stage backend endpoints** (`agent-a`, `agent-b`, `agent-c`, `finalize`) so the UI can advance one stage at a time after `Load Context`.
- **Blocking HIL-1 / HIL-2 / HIL-3 gating** on those per-stage endpoints: 409 when a prior HIL queue still has `NEEDS_REVIEW` or `BLOCKED` items, so manual approval is a real precondition (Task 1 spec).
- **Stage-aware Run Dashboard CTA** in the frontend via `<NextStagePanel>`, keyed off `run.current_stage` + HIL queue size.
- **Inline HIL approve flow** on the run dashboard for HIL-1/2/3 so the reviewer can clear the gate before the next agent runs.
- **Bulk HIL-0 resolution** via `POST /api/v1/runs/{run_id}/hil-0/resolutions/bulk`; the dashboard's "Proceed with flag (n)" button now sends one validated bulk request and avoids Supabase/http2 disconnects caused by parallel request fan-out.
- **Offline `next/font/google` build support**: Inter and JetBrains Mono remain wired through `next/font/google`, with checked-in mocked Google CSS responses and WOFF2 files; `npm run dev` and `npm run build` use webpack for reliable offline compilation on Windows.

Still missing for the final prototype:
- Real Agent B/C adapters using Task 2 structured JSON contracts; Agent A is real-provider capable but Agent B/C still use mock fallback.
- Real Notion adapter with schema preflight, rate limiting, retry with backoff, and dead-letter handling (the repository-level `replay_failed_sync_events` is in place but has no real producer of `SyncStatus.FAILED` events yet).
- LLM-generated GDD version descriptions (`description_status=AI_GENERATED` is modelled but has no producer).
- Correction memory for the Task 4 learning loop.
- Final submission polish: full English pass over `Task-1..4.md`, walkthrough script, screenshots.

## Target End-to-End Demo

The final demo must let a reviewer drive the full pipeline from the frontend, one button click per stage. Each step below corresponds to one HTTP call and one visible state transition on the run dashboard.

1. **Project + GDD picker** — user uploads a GDD and either creates a new project or selects an existing one.
2. **S0 trigger** — `POST /api/v1/runs/trigger` runs rule-based mode detection (`NEW_GAME` for new project, `DELTA` for existing), creates the `Run` at `current_stage=S0_TRIGGER`, and seeds session memory. UI: dashboard opens with "Next: Load Context".
3. **S1 context loader** — `POST /api/v1/runs/{run_id}/context` parses the GDD, registers the `GDDDocument` version, filters actionable sections, builds HIL-0 questions, and (in DELTA) emits `delta_report`. UI: stage badge advances to `S1_CONTEXT_LOADER`; coverage card fills in GDD metadata + section counts. Next CTA = "Resolve HIL-0" if any open questions, else "Run Agent A".
4. **HIL-0 (optional gate)** — reviewer resolves a single clarification question via `POST /api/v1/runs/{run_id}/hil-0/resolutions` or resolves the open batch via `POST /api/v1/runs/{run_id}/hil-0/resolutions/bulk`. Required only when S1 emitted questions; UI hides the panel otherwise.
5. **S2 / S3 — Agent A + Validation A** — `POST /api/v1/runs/{run_id}/agent-a` runs Agent A with bounded retry/repair, persists features, runs `validate_features_with_routing`, records risk events. UI: features tab populates; HIL-1 queue size is now visible.
6. **HIL-1 (blocking gate)** — reviewer approves / rejects features and epic candidates via `POST /api/v1/review-decisions`. Backend refuses Step 7 with `409 hil_gate_blocked` until every `NEEDS_REVIEW` / `BLOCKED` item is cleared.
7. **S4 / S5 — Agent B + Validation B + Sync-A + Sync-B** — `POST /api/v1/runs/{run_id}/agent-b` produces epics/stories/tasks (using `hil_1` session memory of approved features), validates them, mirrors approved epics/stories via Sync-A and approved tasks via Sync-B to the mock or real Notion adapter, updates the kill switch. UI: epics / stories / tasks tabs populate; Sync-A and Sync-B events appear in the sync log.
8. **HIL-2 (blocking gate)** — reviewer clears any `NEEDS_REVIEW` tasks via `POST /api/v1/review-decisions`.
9. **S6 / S7 — Agent C + Validation C + Sync-C** — `POST /api/v1/runs/{run_id}/agent-c` generates the four test-case categories per approved task, validates them, flips approved tasks to `Test Cases Ready`, and syncs test cases via Sync-C.
10. **HIL-3 (blocking gate)** — reviewer clears any flagged test cases.
11. **Finalize** — `POST /api/v1/runs/{run_id}/finalize` builds the coverage report, marks the run `COMPLETED`, and emits `FINAL_COVERAGE`. UI: coverage card flips to "complete"; Sign-off CTA enables.
12. **Sign-off** — `POST /api/v1/runs/{run_id}/sign-off` records reviewer + timestamp; the dashboard's coverage panel renders the green signed-off banner.

Failure paths follow the same contract: each per-stage endpoint either advances the timeline by one stage or returns a structured error (`hil_gate_blocked`, `kill_switch_tripped`, `gdd_not_loaded`, `agent_a_retry_exhausted`, `precondition_failed`).

The legacy `POST /api/v1/demo-runs` route stays for tests and CLI smoke tests — it bundles steps 2–11 with `auto_approve=True` so every HIL gate is treated as cleared. Frontend never calls `/demo-runs`.

## Target Architecture

```text
Next.js frontend
    |
    | /api/v1
    v
FastAPI backend
    |
    +-- PipelineService
    |     +-- S0 trigger, mode detection, run/session initialization
    |     +-- S1 context loader, GDD versioning, parser, HIL-0, DELTA diff
    |     +-- AgentClient: mock + real structured-output LLM provider
    |     +-- deterministic validators and routers
    |     +-- NotionSyncClient: mock + real Sync-A/B/C provider
    |     +-- risk handling, retry, audit, learning loop
    |
    +-- WorkflowRepository
          +-- memory provider
          +-- Supabase provider / knowledge base
```

Architecture rules:

- Backend remains the pipeline source of truth.
- Frontend consumes `/api/v1` only and never reads Supabase directly.
- S0 does not parse, persist, hash, or version the GDD file; it only branches mode and initializes run/session state.
- S1 owns GDD raw loading, version registration, structural parsing, actionability filtering, HIL-0, and DELTA diff.
- Each per-stage endpoint (`agent-a`, `agent-b`, `agent-c`, `finalize`) advances the run by exactly one logical stage block and is idempotent enough to refuse re-entry once it has already produced its artifacts (returns `409 stage_already_advanced`).
- HIL-1, HIL-2, and HIL-3 are **blocking** gates. Each stage endpoint that crosses such a gate verifies the prior tier's review queue is empty (no `NEEDS_REVIEW` / `BLOCKED` items) before doing any work — otherwise `409 hil_gate_blocked` with the offending tier + counts.
- Supabase is the optional persistence and knowledge-base layer for projects, GDD versions, parsed context, generated artifacts, review decisions, correction records, risk events, and sync events.
- Mock provider mode must run without network credentials.
- Real AI must use structured JSON output and schema validation.
- Notion is a destination, not source of truth; replay comes from internal pipeline state.
- Every generated feature, task, and test case must keep source-section traceability.
- Every Notion upsert must preserve `external_id` idempotency and store audit records.

## Delivery Phases

### Phase 0 - Repo And Docs Alignment

- Keep prototype docs aligned with the four source-of-truth solution files.
- Keep current-vs-target behavior explicit so implementers do not confuse MVP code with final design.
- Keep `README.md`, `AGENTS.md`, contracts, runbooks, `PLAN.md`, `TASKS.md`, `backend/PLAN.md`, and `backend/TASKS.md` consistent.

### Phase 1 - Backend Completion By Source-Of-Truth Stages

- S0: implement trigger + mode detection from GDD upload and project selection, create `run_id`, initialize session memory, output `{run_id, project_id, gdd_file, mode}`. ✅ shipped.
- S1: implement raw GDD loading, `GDDDocument` version registration, structural parse, QA-actionability filter, HIL-0 preflight questions, and DELTA diff. ✅ shipped.
- S2/S4/S6: add AgentClient interfaces and real adapters using Task 2 structured JSON contracts. ✅ Agent A shipped; Agent B/C still mock-only.
- S3/S5/S7: expand validators and routers using Task 1 and Task 4 failure handling. ✅ shipped.
- HIL-1/HIL-2/HIL-3: expose review queues and decision endpoints. ✅ read + decision endpoints + blocking-gate enforcement shipped.
- S5b/S7b: implement Task 3 Sync-A/B/C semantics with idempotent `external_id`, throttling, retry, and replay. ✅ mock semantics shipped.
- Final: expand coverage, risk dashboard, and sign-off report. ✅ shipped.

### Phase 1.5 - Stage Orchestration Endpoints (new)

The MVP pipeline originally ran as one synchronous `/demo-runs` batch. This phase is now implemented: production UX has one endpoint per advanceable stage so the frontend can present the workflow as a stepped wizard.

- Extract `_stage_s2_agent_a`, `_stage_s4_agent_b`, `_stage_s6_agent_c`, `_stage_finalize` methods on `PipelineService`. `run_demo()` becomes a thin wrapper that calls them in sequence with `auto_approve=True`.
- Add `POST /api/v1/runs/{run_id}/agent-a` — preconditions: `current_stage == S1_CONTEXT_LOADER`, every HIL-0 question is resolved (or skipped). Effect: runs Agent A retry loop + Validation A; persists features + issues + risk events; advances to `S3_VALIDATION_A`.
- Add `POST /api/v1/runs/{run_id}/agent-b` — preconditions: `current_stage in {S3_VALIDATION_A}`, HIL-1 queue is empty (no `NEEDS_REVIEW` / `BLOCKED` features or epics). Effect: builds HIL-1 session snapshot from current approvals, runs Agent B, validates tasks, runs Sync-A + Sync-B, updates kill switch; advances to `S5_VALIDATION_B_SYNC` (or marks the run failed when the kill switch trips).
- Add `POST /api/v1/runs/{run_id}/agent-c` — preconditions: `current_stage == S5_VALIDATION_B_SYNC`, HIL-2 queue empty. Effect: runs Agent C, validates test cases, runs Sync-C, flips approved tasks to `Test Cases Ready`; advances to `S7_VALIDATION_C_SYNC`.
- Add `POST /api/v1/runs/{run_id}/finalize` — preconditions: `current_stage == S7_VALIDATION_C_SYNC`, HIL-3 queue empty. Effect: builds the coverage report, sets `status=COMPLETED`, advances to `FINAL_COVERAGE`.
- Each endpoint must return a uniform error shape on precondition failure: HTTP 409 with `error.code in {wrong_stage, hil_gate_blocked, kill_switch_tripped, gdd_not_loaded}` and `error.details` carrying the offending counts / required next action.

The `auto_approve=True` knob on `/demo-runs` remains the way to bypass HIL gates in tests and CLI smoke runs. Frontend never sends it.

### Phase 2 - Real AI And Real Notion

- Add real LLM provider with structured output, low temperature, schema validation, retry/repair policy, and raw output logging.
- Add real Notion provider with schema preflight, external-id upsert, page-id relation mapping, conflict detection, rate limiting, and dead-letter queue.
- Preserve mock fallback for local demo and tests.

### Phase 3 - Frontend Demo App

- Project selection/create screen that drives S0 mode detection. ✅ shipped.
- GDD upload and GDD version history screens owned by S1 behavior. ✅ shipped.
- Run dashboard and timeline. ✅ shipped (timeline + coverage cards + agent runs + artifact tabs).
- **Stage-aware advance CTA on the run dashboard.** Replace the standalone `Load Context` button with a `<NextStagePanel>` that:
  - reads `run.current_stage`, the HIL-0 question count, and the relevant HIL queue size,
  - picks the right mutation (`useLoadContext`, `useRunAgentA`, `useRunAgentB`, `useRunAgentC`, `useFinalizeRun`),
  - shows a "blocked by HIL-X review" state with a "Resolve queue" deep link when the prior gate has open items.
- **Inline HIL approve flow** — when the next gate is HIL-1/2/3, render the matching review queue right under the CTA with per-item Approve / Reject buttons (calls `useCreateReviewDecision`) and a bulk "Approve all in queue" shortcut. Same UI works embedded on the dashboard and on the future `/runs/[run_id]/hil/[tier]` route.
- HIL-0 / HIL-1 / HIL-2 / HIL-3 dedicated review screens (Phase F4 in `frontend/TASKS.md`) are still planned for screenshots and deep links, but the inline flow above is enough to drive the E2E walkthrough.
- Feature, task, test-case, sync-event, risk, and coverage views.

### Phase 4 - End-to-End Verification And Submission Polish

- Run backend tests and lint.
- Run frontend lint/build.
- Run mock-mode end-to-end demo.
- Run real AI + real Notion smoke test when credentials are configured.
- Capture screenshots or a short walkthrough script.
- Update README with final demo commands.

## Public Interfaces To Preserve

- API response envelope: `{ "data": ..., "meta": ..., "error": ... }`.
- Base API prefix: `/api/v1`.
- Existing `/api/v1/demo-runs` behavior.
- Existing run inspection endpoints for timeline, coverage, sections, features, tasks, test cases, validation issues, and sync events.
- `external_id` as the Notion idempotency key.
- `source_sections` on generated features, tasks, and test cases.
- Mock mode as the default local demo path.

Planned API additions:

Already landed:

- `POST /api/v1/projects`
- `GET /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `POST /api/v1/runs/trigger`
- `POST /api/v1/runs/{run_id}/context`
- `GET /api/v1/projects/{project_id}/gdd-documents`
- `GET /api/v1/runs/{run_id}/epics`
- `GET /api/v1/runs/{run_id}/stories`
- `GET /api/v1/runs/{run_id}/agent-runs`
- `GET /api/v1/runs/{run_id}/review-decisions`
- `GET /api/v1/runs/{run_id}/risk-events`
- `GET /api/v1/providers/status`

Landed in Phase 1.5:

- `POST /api/v1/runs/{run_id}/agent-a` — advance S1 → S3 with HIL-0 precondition.
- `POST /api/v1/runs/{run_id}/agent-b` — advance S3 → S5 with HIL-1 precondition + Sync-A/B.
- `POST /api/v1/runs/{run_id}/agent-c` — advance S5 → S7 with HIL-2 precondition + Sync-C.
- `POST /api/v1/runs/{run_id}/finalize` — advance S7 → `FINAL_COVERAGE` with HIL-3 precondition.
- `POST /api/v1/runs/{run_id}/hil-0/resolutions/bulk` — resolve the open HIL-0 batch in one request.

## Acceptance Criteria

The prototype is complete when:

- A user can start backend with one documented command.
- A user can start frontend with one documented command.
- A user can upload a GDD and choose new project vs existing project, and S0 sets `NEW_GAME` or `DELTA` correctly.
- S1 registers/loads/parses GDD versions and produces HIL-0 questions and DELTA diff when needed.
- **The reviewer can complete the full stepped walkthrough from the UI: trigger → Load Context → Agent A → HIL-1 approve → Agent B → HIL-2 approve → Agent C → HIL-3 approve → Finalize → Sign-off, with one button click per stage and no terminal access required.**
- Skipping a HIL approval produces a clear blocked-state CTA on the dashboard instead of a silent failure.
- A real AI + real Notion smoke test works when credentials and Notion schema are configured.
- Frontend shows GDD version metadata, validation issues, review actions, sync events, risk state, and final coverage.
- Backend tests pass, including new tests for per-stage endpoints + HIL gating.
- Frontend build/lint passes.
- README includes final demo walkthrough.
