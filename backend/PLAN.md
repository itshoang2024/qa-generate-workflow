# Backend Completion Plan

## Goal

Complete the backend as the source of truth for the prototype pipeline: ingest a game design document, generate QA planning artifacts, validate every stage, support human review, sync to Notion, and expose all data needed by the frontend demo through `/api/v1`.

The backend must keep `AI_PROVIDER=mock` and `NOTION_PROVIDER=mock` as the stable default path. Real AI, real Notion, and Supabase persistence are target capabilities, but the local demo must remain deterministic without external credentials.

## Current Backend State

- FastAPI app, versioned routes, domain models, repository abstraction, mock pipeline, validators, mock Notion sync, Snake Escape fixture, Supabase schema, and tests exist.
- `POST /api/v1/demo-runs` runs the seeded Snake Escape flow and produces sections, features, tasks, test cases, validation issues, coverage, and sync events.
- The current flow is enough for a Swagger demo but still needs stronger stage boundaries, real adapter interfaces, richer HIL behavior, real sync validation, and frontend-oriented query endpoints.

## Stage-Based Plan

### S0 Trigger + Mode Detection

S0 normalizes the incoming work request into a project, run, and pipeline mode.

Current behavior:

- Demo mode creates a run and executes the Snake Escape pipeline.
- `NEW_GAME` is effectively the only supported mode.

Target behavior:

- Support `NEW_GAME` fully for upload/select GDD workflows.
- Keep `DELTA` modeled as a first-class mode, but implement it in a later explicit phase.
- Normalize project creation, run creation, source document metadata, and execution options before any agent work starts.
- Preserve idempotent run metadata so API clients can safely refresh or replay sync operations.

Backend outputs:

- `Project`
- `Run`
- mode metadata: `NEW_GAME` or `DELTA`
- initial timeline events

Acceptance:

- `/demo-runs` still creates a deterministic run.
- Future frontend can create/select a run without knowing internal pipeline details.

### S1 Context Loader

S1 converts source documents into structured, traceable context for agents and validators.

#### S1.1 Structural DOCX Parsing

Current behavior:

- Parser extracts Snake Escape content into sections from the tracked sample GDD.

Target behavior:

- Harden source path handling for selected files and bundled fixtures.
- Preserve heading hierarchy, paragraph text, tables, lists, special notes, and source order.
- Assign stable `section_id` values that downstream agents can cite.
- Record source metadata needed for audit and frontend inspection.

Acceptance:

- Parser tests prove headings, tables, and special notes are extracted.
- Every generated artifact can reference at least one source section.

#### S1.2 QA-Actionability Filter

Current behavior:

- Mock fixture already implies useful sections for generation.

Target behavior:

- Classify sections by QA relevance: mechanics, rules, UI, levels, scoring, monetization, technical notes, and unclear notes.
- Exclude or down-rank sections that are not actionable for QA.
- Surface low-confidence or ambiguous sections for preflight review.

Acceptance:

- Feature generation receives only traceable, relevant context.
- Non-actionable content does not create noisy QA tasks.

#### S1.3 HIL-0 Preflight Clarification

Current behavior:

- No dedicated preflight review model/API.

Target behavior:

- Add a preflight issue model for missing, contradictory, or unclear GDD requirements.
- Expose an API for listing and resolving preflight issues.
- Allow the pipeline to proceed in mock demo mode while recording unresolved assumptions.

Acceptance:

- Frontend can show "needs clarification" before Agent A.
- Pipeline records assumptions instead of silently hiding ambiguity.

#### S1.4 DELTA Diff

Current behavior:

- Not implemented.

Target behavior:

- Model the diff between a previous source document and a revised source document.
- Detect added, removed, and changed sections.
- Route only changed context to affected downstream artifacts.

Acceptance:

- DELTA is documented and represented in models before full implementation.
- Later work can add partial regeneration without changing public contracts.

### S2 Agent A - GDD Analyzer

S2 turns structured GDD context into features and epics.

Current behavior:

- Mock Agent A returns deterministic feature output from `snake_escape_fixture.json`.

Target behavior:

- Formalize an `AgentClient` interface with mock and real implementations.
- Keep the mock fixture as default and as fallback.
- Add a real LLM adapter behind environment configuration.
- Require structured JSON output matching the domain contract.
- Preserve source section citations and confidence scores.

Acceptance:

- Mock output remains byte-stable enough for tests.
- Real provider failures can fall back to mock or return a clear validation issue.
- Agent A output never bypasses schema validation.

### S3 Validation A + Router A

S3 validates Agent A output and assigns each item to a routing lane.

Current behavior:

- Validation covers source references and confidence issues.

Target behavior:

- Expand schema validation for missing fields, invalid source sections, low confidence, duplicate feature names, and incomplete epic grouping.
- Add router lane output: `auto`, `needs_review`, or `blocked`.
- Store validation issues with codes, severity, source artifact, and suggested resolution.

Acceptance:

- Good mock features enter `auto`.
- Low-confidence or weakly sourced features enter `needs_review`.
- Structurally invalid features enter `blocked`.

### HIL-1 Epic-Level Review

HIL-1 lets a reviewer approve, edit, reject, or unblock feature and epic decisions.

Current behavior:

- `POST /review-decisions` exists as a generic review decision endpoint.

Target behavior:

- Support review decisions against features and epics.
- Keep behavior consistent between memory repository and Supabase repository.
- Record reviewer role, decision, note, timestamp, and target artifact.
- Expose enough listing/filtering support for frontend review queues.

Acceptance:

- A reviewer can approve or reject a feature before Agent B consumes it.
- Decisions are auditable and do not erase the original agent output.

### S4 Agent B - QA Planner

S4 expands approved features into epics, stories, and QA tasks.

Current behavior:

- Mock Agent B returns deterministic task output from the fixture.

Target behavior:

- Use the same `AgentClient` interface pattern as Agent A.
- Generate epics, stories, and QA tasks with explicit parent-child references.
- Apply deterministic QA assignee mapping from the seeded QA roster.
- Require real provider output to preserve the JSON contract exactly.
- Include priority, estimate, acceptance criteria, source references, and confidence.

Acceptance:

- Agent B tasks can be rendered in frontend boards and synced to Notion.
- Invalid assignees, duplicate task IDs, and missing references are caught before sync.

### S5 Validation B + Router B + HIL-2

S5 validates QA planning output and routes task-level review.

Current behavior:

- Validation checks duplicate tasks, bad assignee values, low confidence, and idempotent external IDs.

Target behavior:

- Expand validation issue codes for duplicate external IDs, invalid parent references, missing acceptance criteria, weak source coverage, and invalid task state.
- Add router lanes for auto-sync, task review, and blocked sync.
- Support HIL-2 decisions for task approval, edit request, rejection, and manual assignee override.

Acceptance:

- Only valid auto-lane tasks are eligible for Notion sync.
- Review decisions can move a task from review/blocked to sync-ready.

### S5b Notion Task Sync

S5b syncs QA tasks to Notion and preserves auditability.

Current behavior:

- Mock Notion sync records sync payloads and events.

Target behavior:

- Formalize a `NotionSyncClient` interface with mock and real implementations.
- Implement real Notion upsert by stable `external_id`.
- Validate Notion database schema before writing.
- Store request payload, response payload, status, and error information in `SyncEvent`.
- Keep sync replay idempotent.

Acceptance:

- Mock sync remains deterministic for demo and tests.
- Real sync can be smoke-tested when credentials are configured.
- Replaying sync does not create duplicate Notion pages.

### S6 Agent C - Test Case Generator

S6 generates test cases from approved QA tasks.

Current behavior:

- Mock Agent C returns deterministic test cases from the fixture.

Target behavior:

- Use the shared `AgentClient` interface.
- Generate four categories per eligible task: functional, edge, negative, and regression.
- Preserve task references, source sections, confidence, preconditions, steps, expected results, and priority.
- Allow per-task parallelism later without changing the public result shape.

Acceptance:

- Each synced/approved QA task has a balanced test case set.
- Real provider output is validated before storage or sync.

### S7 Validation C + HIL-3

S7 validates test cases and routes final review.

Current behavior:

- Validation checks broad coverage and source links.

Target behavior:

- Validate category coverage per task.
- Validate source links, task links, missing expected results, duplicate cases, weak confidence, and impossible preconditions.
- Support HIL-3 review decisions for generated test cases.

Acceptance:

- Coverage gaps become validation issues with actionable codes.
- Frontend can show review queues for test case corrections.

### S7b Test Case Sync

S7b syncs validated test cases to Notion.

Current behavior:

- Mock sync records test case payloads.

Target behavior:

- Use the real Notion adapter for test case databases.
- Upsert by `external_id`.
- Preserve sync audit records separately from task sync events.
- Support sync replay for failed or changed test cases.

Acceptance:

- Test case sync is idempotent.
- Sync events expose enough payload detail for demo inspection and debugging.

### Final Coverage Report + Sign-off

The final stage summarizes pipeline quality and readiness.

Current behavior:

- Coverage data is exposed through `/runs/{run_id}/coverage`.

Target behavior:

- Store a coverage report with totals, task coverage, category coverage, source coverage, validation issue summary, sync summary, and reviewer sign-off state.
- Expose report APIs for frontend summary screens and submission screenshots.
- Prepare a final demo report export or printable view.

Acceptance:

- One run can show end-to-end traceability from GDD section to feature, task, test case, validation issue, sync event, and sign-off.
- Mock mode can produce the complete report with no external services.

## Cross-Cutting Backend Requirements

- All public API responses keep the `{ data, meta, error }` envelope.
- Mock providers remain the default for local demo and tests.
- Supabase persistence remains optional and must not be required for the default demo.
- Real providers are enabled only through explicit environment configuration.
- Every external write path records an audit event before returning success.
- Validation issues must use stable codes so frontend filters and documentation remain reliable.

## Backend Acceptance Criteria

- `pytest` passes in `backend/`.
- `python -m ruff check .` passes in `backend/`.
- Swagger can create a demo run and inspect timeline, coverage, sections, features, tasks, test cases, validation issues, and sync events.
- Mock mode remains deterministic.
- Real AI and Notion paths can be smoke-tested when credentials are present, without breaking mock mode.
