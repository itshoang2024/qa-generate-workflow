# Backend Stage Tasks

This checklist tracks the backend work needed to complete the prototype pipeline. Each task includes a verification step so implementation can proceed stage by stage without relying on hidden assumptions.

## Phase S0 - Trigger + Mode Detection

- [ ] Task: Add or confirm project/run creation APIs for non-demo frontend flows.
  Verify: Creating a project/run returns `{ data, meta, error }` and stores mode metadata.

- [ ] Task: Keep `NEW_GAME` as the fully supported execution mode.
  Verify: `POST /api/v1/demo-runs` creates a run with a complete timeline in mock mode.

- [ ] Task: Model `DELTA` mode in domain types and request metadata without enabling partial regeneration yet.
  Verify: Tests confirm `DELTA` is accepted or explicitly rejected with a stable error code, not an unhandled exception.

- [ ] Task: Normalize source document metadata during run creation.
  Verify: Run detail includes source filename/path metadata needed by the frontend.

## Phase S1 - Context Loader

- [ ] Task: Harden GDD path handling for bundled fixtures and future upload/select flows.
  Verify: Parser tests pass for the tracked Snake Escape DOCX copy and fail clearly for missing files.

- [ ] Task: Expand parser tests for headings, tables, ordered content, and special notes.
  Verify: Tests assert extracted section titles, table text, special notes, and stable section order.

- [ ] Task: Add section classification for QA-actionable context.
  Verify: Tests show mechanics, UI, levels, scoring, and unclear notes receive expected classifications.

- [ ] Task: Add preflight issue domain model for HIL-0 clarifications.
  Verify: Preflight issues can be stored and listed through repository tests or API tests.

- [ ] Task: Add HIL-0 API support for listing and resolving preflight issues.
  Verify: API tests can create a run, list preflight issues, resolve one, and inspect the audit trail.

- [ ] Task: Document and stub S1.4 DELTA diff data shape.
  Verify: Backend plan, contracts, and domain types agree on added/changed/removed section fields.

## Phase S2 - Agent A

- [ ] Task: Introduce a shared `AgentClient` interface for agent calls.
  Verify: Mock Agent A uses the interface without changing current demo output.

- [ ] Task: Keep fixture-backed mock Agent A as the default provider.
  Verify: Tests pass with no AI credentials configured.

- [ ] Task: Add real AI provider selection behind `AI_PROVIDER`.
  Verify: Setting an unsupported provider returns a clear startup or request error.

- [ ] Task: Enforce structured Agent A output before persistence.
  Verify: Invalid mock/fixture mutations fail validation with stable issue codes.

## Phase S3 - Validation A + Router A

- [ ] Task: Expand Agent A validation issue codes for schema, source, confidence, duplicate, and incomplete grouping failures.
  Verify: Unit tests cover each issue code.

- [ ] Task: Add router lane fields for Agent A artifacts: `auto`, `needs_review`, and `blocked`.
  Verify: Low-confidence features route to `needs_review`; invalid features route to `blocked`.

- [ ] Task: Expose Agent A validation and routing state through run detail endpoints.
  Verify: API response for features includes enough state for frontend review queues.

## Phase HIL-1 - Epic-Level Review

- [ ] Task: Extend review decisions for feature and epic targets.
  Verify: `POST /api/v1/review-decisions` accepts feature/epic target types and rejects unknown targets.

- [ ] Task: Ensure review behavior parity between memory and Supabase repositories.
  Verify: Repository contract tests pass for both backends or for a Supabase-compatible test double.

- [ ] Task: Add review listing endpoints if required by frontend queues.
  Verify: Frontend can query pending feature/epic review items without scanning every artifact manually.

## Phase S4 - Agent B

- [ ] Task: Move Agent B behind the shared `AgentClient` interface.
  Verify: Demo run still creates deterministic epics, stories, and tasks.

- [ ] Task: Preserve parent-child references from feature to epic/story/task.
  Verify: Tests assert every task links to a valid story/epic/feature path.

- [ ] Task: Apply deterministic assignee mapping from the QA roster.
  Verify: Validation accepts seeded assignees and rejects unknown assignees.

- [ ] Task: Add real Agent B adapter path behind `AI_PROVIDER`.
  Verify: Real provider output must parse through the same Pydantic/domain contract as mock output.

## Phase S5 - Validation B + Router B + HIL-2

- [ ] Task: Expand task validation issue codes for duplicate external IDs, invalid parents, bad assignees, missing acceptance criteria, and weak source coverage.
  Verify: Unit tests cover each issue code.

- [ ] Task: Add task router lane fields for auto-sync, needs review, and blocked sync.
  Verify: Duplicate or invalid tasks cannot enter the sync-ready lane.

- [ ] Task: Add HIL-2 decisions for task approval, edit request, rejection, and assignee override.
  Verify: API tests show review decisions change task review state without deleting original agent output.

- [ ] Task: Ensure idempotent external IDs before sync.
  Verify: Re-running validation on the same run does not create new external IDs for existing tasks.

## Phase S5b - Notion Task Sync

- [ ] Task: Introduce a `NotionSyncClient` interface with mock and real providers.
  Verify: Mock sync still records payloads in `sync_events`.

- [ ] Task: Implement real Notion task upsert by `external_id`.
  Verify: Notion smoke test updates an existing page instead of creating a duplicate when credentials are configured.

- [ ] Task: Add Notion task database schema validation.
  Verify: Missing required Notion properties produce a blocked sync issue before write attempts.

- [ ] Task: Add sync replay behavior for failed or selected task sync events.
  Verify: API test for `/api/v1/runs/{run_id}/sync-replay` proves replay is idempotent.

## Phase S6 - Agent C

- [ ] Task: Move Agent C behind the shared `AgentClient` interface.
  Verify: Demo run still creates deterministic test cases from the fixture.

- [ ] Task: Generate functional, edge, negative, and regression categories for eligible tasks.
  Verify: Tests assert each eligible task has all required categories or a validation issue.

- [ ] Task: Preserve task links, source links, preconditions, steps, expected results, priority, and confidence.
  Verify: API tests inspect a test case and confirm all frontend-required fields are present.

- [ ] Task: Prepare Agent C for future per-task parallelism.
  Verify: Interface accepts task-scoped inputs and returns mergeable task-scoped outputs.

## Phase S7 - Validation C + HIL-3

- [ ] Task: Expand test case validation issue codes for category gaps, missing expected results, duplicate cases, invalid task links, invalid source links, and weak confidence.
  Verify: Unit tests cover each issue code.

- [ ] Task: Add test case router lanes for auto-sync, needs review, and blocked sync.
  Verify: Invalid test cases cannot enter the sync-ready lane.

- [ ] Task: Add HIL-3 decisions for test case approval, edit request, and rejection.
  Verify: API tests show decisions are persisted and exposed in review queues.

## Phase S7b - Test Case Sync

- [ ] Task: Implement real Notion test case upsert by `external_id`.
  Verify: Notion smoke test updates existing test case pages when credentials are configured.

- [ ] Task: Add Notion test case database schema validation.
  Verify: Missing required properties produce a clear sync validation issue.

- [ ] Task: Preserve separate task sync and test case sync audit trails.
  Verify: `/api/v1/runs/{run_id}/sync-events` distinguishes artifact type and payload kind.

- [ ] Task: Add sync replay coverage for test cases.
  Verify: Replay test confirms no duplicate Notion pages are produced.

## Phase Final - Coverage Report + Sign-off

- [ ] Task: Add coverage report persistence if current coverage is computed only in memory.
  Verify: Run detail and coverage endpoints return the same report after repository reload.

- [ ] Task: Expand coverage/report API for frontend summary screens.
  Verify: API response includes totals, source coverage, task coverage, category coverage, validation summary, sync summary, and sign-off state.

- [ ] Task: Add reviewer sign-off model and endpoint.
  Verify: API tests can record sign-off and show it in the final report.

- [ ] Task: Prepare final demo report payload.
  Verify: One endpoint or documented sequence can produce all data needed for submission screenshots.

## Final Backend Verification

- [ ] Task: Run the backend test suite.
  Verify: `conda run -n qa-generator python -m pytest` passes from `backend/`.

- [ ] Task: Run backend linting.
  Verify: `conda run -n qa-generator python -m ruff check .` passes from `backend/`.

- [ ] Task: Run manual Swagger demo.
  Verify: `POST /api/v1/demo-runs` creates a run, and timeline, coverage, tasks, test cases, validation issues, and sync payloads are inspectable.

- [ ] Task: Run Notion smoke test when credentials are configured.
  Verify: A task and a test case are upserted by `external_id`, then replay updates the same pages.

- [ ] Task: Confirm mock fallback remains stable.
  Verify: Removing AI, Notion, and Supabase credentials still allows the complete demo run to finish.
