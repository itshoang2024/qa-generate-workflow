# End-to-End Prototype Completion Plan

## Goal

Complete `qa-generate-workflow` as a credible end-to-end webapp prototype for the SUN.RISER Round 2 homework submission. The source of truth for product behavior is the four root-level solution files:

- `Task-1-AI-workflow-design.md`
- `Task-2-Agent-prompts-JSON.md`
- `Task-3-Sync-to-Notion.md`
- `Task-4-Risk-Failure-handling.md`

The prototype should show how a GDD upload and project selection become a mode-aware QA workflow, then a reviewable execution plan with features, tasks, test cases, validation gates, human review, Notion sync records, risk handling, and a coverage/sign-off report.

Mock mode remains mandatory for a stable local demo. Real AI, real Notion, Supabase persistence, DELTA processing, and LLM-generated GDD version descriptions are target capabilities.

## Current State (last reviewed 2026-05-11)

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
- Project APIs (`POST/GET /api/v1/projects`, `GET /api/v1/projects/{id}`), S0 trigger (`POST /api/v1/runs/trigger`), S1 context (`POST /api/v1/runs/{run_id}/context`), GDD version history (`GET /api/v1/projects/{project_id}/gdd-documents`), HIL-0 questions/resolutions APIs, and DELTA diff with `NEW`/`MODIFIED`/`UNCHANGED`/`REMOVED` buckets.
- Provider readiness endpoint `GET /api/v1/providers/status` reporting AI / Notion / repository credential state.
- In-memory repository by default and optional Supabase repository, with full parity across projects, runs, GDD documents, sections, HIL-0 questions/resolutions, agent runs, review decisions, and sync events.
- Risk event model/API, kill switch, reviewer sign-off endpoint, and coverage report extensions for `risk_summary`, `sync_summary`, `gdd_version_metadata`, and `sign_off`.
- Supabase schema in `supabase/schema.sql` including `runs` upgrades for `session_memory`, `gdd_document_id`, `source_version_id`, `source_metadata`, `delta_report`, and generated artifact/risk/sync tables.
- Backend tests (parser, validators, pipeline, agents, API, config, supabase schema) covering the demo counts, S0 split, S1 versioning + DELTA, HIL queues, and review-decision lane updates.
- Docs, contracts, runbooks, fixture guide, and planning docs.

Still missing for the final prototype:

- Real Agent B/C adapters using Task 2 structured JSON contracts; Agent A is real-provider capable but Agent B/C still use mock fallback.
- Real Notion adapter with schema preflight, rate limiting, retry with backoff, and dead-letter handling (the repository-level `replay_failed_sync_events` is in place but has no real producer of `SyncStatus.FAILED` events yet).
- LLM-generated GDD version descriptions (`description_status=AI_GENERATED` is modelled but has no producer).
- Correction memory for the Task 4 learning loop.
- Frontend app (`frontend/` is not scaffolded).
- Final submission polish: full English pass over `Task-1..4.md`, walkthrough script, screenshots.

## Target End-to-End Demo

The final demo should support this flow:

1. User opens the frontend dashboard.
2. User uploads a GDD and either creates a new project or selects an existing project.
3. S0 runs rule-based mode detection:
   - existing project selected -> `mode=DELTA`
   - new project created -> `mode=NEW_GAME`
   - create `run_id`
   - initialize session memory
   - output `{run_id, project_id, gdd_file, mode}`
4. S1 loads the raw GDD, registers the GDD document version, structurally parses the file, filters QA-actionable sections, and prepares HIL-0 clarification questions.
5. If mode is `DELTA`, S1.4 compares the new GDD version with the previous version and produces `delta_report`.
6. Agent A produces a grounded feature inventory using Task 2 JSON contracts and source-section traceability.
7. Validation A checks schema, traceability, keyword overlap, coverage, and confidence, then routes to auto, HIL-1, or block.
8. QA Lead approves or corrects features and epic grouping in HIL-1.
9. Notion Sync-A creates/updates Epic and Story records after HIL-1 approval.
10. Agent B produces stories and QA tasks from approved features, epic grouping, and per-game memory.
11. Validation B checks schema, cross-agent references, dedup, assignee mapping, confidence, and router lanes.
12. Notion Sync-B creates/updates task records after HIL-2 or auto-approval.
13. Agent C runs per approved task, in parallel where possible, and generates positive, negative, edge, and integration test cases.
14. Validation C checks schema, traceability, category coverage, repeatability, and forbidden vague test data.
15. Notion Sync-C appends/updates test cases after HIL-3 or auto-approval.
16. Final report shows section/story coverage, assignee distribution, priority distribution, risk metrics, sync status, GDD version metadata, and sign-off state.

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

- S0: implement trigger + mode detection from GDD upload and project selection, create `run_id`, initialize session memory, output `{run_id, project_id, gdd_file, mode}`.
- S1: implement raw GDD loading, `GDDDocument` version registration, structural parse, QA-actionability filter, HIL-0 preflight questions, and DELTA diff.
- S2/S4/S6: add AgentClient interfaces and real adapters using Task 2 structured JSON contracts.
- S3/S5/S7: expand validators and routers using Task 1 and Task 4 failure handling.
- HIL-1/HIL-2/HIL-3: expose review queues and decision endpoints.
- S5b/S7b: implement Task 3 Sync-A/B/C semantics with idempotent `external_id`, throttling, retry, and replay.
- Final: expand coverage, risk dashboard, and sign-off report.

### Phase 2 - Real AI And Real Notion

- Add real LLM provider with structured output, low temperature, schema validation, retry/repair policy, and raw output logging.
- Add real Notion provider with schema preflight, external-id upsert, page-id relation mapping, conflict detection, rate limiting, and dead-letter queue.
- Preserve mock fallback for local demo and tests.

### Phase 3 - Frontend Demo App

- Project selection/create screen that drives S0 mode detection.
- GDD upload and GDD version history screens owned by S1 behavior.
- Run dashboard and timeline.
- HIL-0/HIL-1/HIL-2/HIL-3 review screens.
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

## Acceptance Criteria

The prototype is complete when:

- A user can start backend with one documented command.
- A user can start frontend with one documented command.
- A user can upload a GDD and choose new project vs existing project, and S0 sets `NEW_GAME` or `DELTA` correctly.
- S1 registers/loads/parses GDD versions and produces HIL-0 questions and DELTA diff when needed.
- A mock-mode demo run completes from frontend and exposes all major artifacts.
- A real AI + real Notion smoke test works when credentials and Notion schema are configured.
- Frontend shows GDD version metadata, validation issues, review actions, sync events, risk state, and final coverage.
- Backend tests pass.
- Frontend build/lint passes.
- README includes final demo walkthrough.
