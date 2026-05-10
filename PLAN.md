# End-to-End Prototype Completion Plan

## Goal

Complete `qa-generate-workflow` as a credible end-to-end webapp prototype for the SUN.RISER Round 2 homework submission. The final demo should show how a GDD becomes a reviewable QA execution plan with feature inventory, QA tasks, test cases, validation gates, human review actions, Notion sync records, and a coverage/sign-off report.

The prototype must be impressive enough for demo, but still safe to run. Real AI and real Notion are target capabilities; mock mode remains mandatory as the stable fallback.

## Current State

Already implemented:

- FastAPI backend under `backend/`.
- Synchronous Snake Escape demo pipeline through `/api/v1/demo-runs`.
- DOCX parser for the sample GDD.
- Mock Agent A/B/C behavior from `data/snake_escape_fixture.json`.
- Deterministic validators for source traceability, confidence, assignee sanity, duplicate candidates, and test-case category coverage.
- Mock Notion sync events with `external_id` idempotency shape.
- In-memory repository by default and optional Supabase repository.
- Supabase schema in `supabase/schema.sql`.
- Backend tests, docs, contracts, runbooks, and fixture guide.

Still missing for the final prototype:

- Frontend app.
- Real AI provider adapter.
- Real Notion adapter.
- Full review routing behavior for HIL-0/HIL-1/HIL-2/HIL-3.
- Robust config loading and provider readiness checks.
- End-to-end demo script, screenshots, and submission polish.
- Delta workflow beyond modeled enum support.

## Target End-to-End Demo

The final demo should support this flow:

1. User opens the frontend dashboard.
2. User selects the Snake Escape GDD demo preset or uploads/selects the tracked sample GDD.
3. Backend creates a run and shows stage timeline from S0 to Final.
4. Backend parses GDD sections and highlights actionable, skipped, ambiguous, and flagged sections.
5. Agent A produces feature inventory with source sections and confidence.
6. Validation A produces issues and router lanes.
7. QA Lead reviews low-confidence features and epic grouping.
8. Agent B produces epics, stories, and QA tasks with deterministic assignees.
9. Validation B flags duplicates, bad references, low-confidence tasks, and assignee issues.
10. Approved tasks sync to Notion through real Notion adapter when configured, or mock sync when not.
11. Agent C creates positive, negative, edge, and integration test cases per approved task.
12. Validation C checks source links and category coverage.
13. Test cases sync to Notion.
14. Frontend shows coverage, assignee distribution, priority distribution, validation issues, and sync status.
15. Demo ends with a sign-off report and links to Notion records or mock sync payloads.

## Target Architecture

```text
Next.js frontend
    |
    | /api/v1
    v
FastAPI backend
    |
    +-- PipelineService
    |     +-- S0/S1 parser and mode detection
    |     +-- AgentClient: mock + real LLM provider
    |     +-- validators and routers
    |     +-- NotionSyncClient: mock + real Notion provider
    |
    +-- WorkflowRepository
          +-- memory provider
          +-- Supabase provider
```

Architecture rules:

- Backend remains the pipeline source of truth.
- Frontend consumes `/api/v1` only and never reads Supabase directly.
- Mock provider mode must run without network credentials.
- Real AI and real Notion must be enabled by environment variables.
- Every generated feature, task, and test case must keep source-section traceability.
- Every Notion upsert must preserve `external_id` idempotency and store `SyncEvent` audit records.

## Delivery Phases

### Phase 0 - Repo And Config Hardening

Make the current backend and docs easier to run and safer to extend.

- Normalize GDD path behavior around the tracked GDD copy.
- Decide whether to load `.env` explicitly or document shell-only env usage everywhere.
- Add missing project-level plans and tasks.
- Keep `README.md`, `AGENTS.md`, and docs contracts aligned.

### Phase 1 - Backend API Completion

Close backend gaps that the frontend and demo need.

- Add read endpoints for epics, stories, and agent runs.
- Add review-decision listing endpoints.
- Add provider readiness endpoint or fields in `/health`.
- Add router-lane fields for auto, needs-review, and blocked outputs.
- Align in-memory and Supabase review-decision behavior.
- Expand test coverage for low-confidence, blocked, review, and replay paths.

### Phase 2 - Real AI And Real Notion

Implement real provider adapters while preserving mock fallback.

- Introduce formal `AgentClient` interface for Agent A, Agent B, and Agent C.
- Add real LLM adapter with structured JSON output and schema validation.
- Introduce formal `NotionSyncClient` interface.
- Add real Notion adapter with create/update by `external_id`.
- Add Notion schema preflight validation.
- Add provider-level error handling, retry metadata, and safe fallback documentation.

### Phase 3 - Frontend Demo App

Create a Next.js + TypeScript frontend for the evaluator-facing demo.

- Run dashboard and pipeline timeline.
- Section viewer with actionable/skipped/ambiguous states.
- Feature review view for HIL-1.
- Task board grouped by epic/story/assignee for HIL-2.
- Test-case review view for HIL-3.
- Sync-events view for mock/real Notion records.
- Coverage/sign-off report.

### Phase 4 - End-to-End Verification And Submission Polish

Prepare the final demo path.

- Run backend tests and lint.
- Run frontend lint/build.
- Run mock-mode end-to-end demo.
- Run real AI + real Notion smoke test when credentials are configured.
- Capture screenshots or a short walkthrough script.
- Update README with final demo commands.

## Public Interfaces To Preserve

- API response envelope: `{ "data": ..., "meta": ..., "error": ... }`.
- Base API prefix: `/api/v1`.
- Existing run inspection endpoints for timeline, coverage, sections, features, tasks, test cases, validation issues, and sync events.
- `external_id` as the Notion idempotency key.
- `source_sections` on generated features, tasks, and test cases.
- Mock mode as the default local demo path.

Planned API additions:

- `GET /api/v1/runs/{run_id}/epics`
- `GET /api/v1/runs/{run_id}/stories`
- `GET /api/v1/runs/{run_id}/agent-runs`
- `GET /api/v1/runs/{run_id}/review-decisions`
- `GET /api/v1/providers/status`

## Demo Fallback Strategy

Real integrations are optional at demo time. If AI or Notion credentials are missing or fail:

- `AI_PROVIDER=mock` uses deterministic fixture output.
- `NOTION_PROVIDER=mock` stores sync events without calling Notion.
- Frontend must display provider mode clearly.
- Coverage, validation, review, and sync-event screens should still be useful in mock mode.

## Acceptance Criteria

The prototype is complete when:

- A user can start backend with one documented command.
- A user can start frontend with one documented command.
- A mock-mode demo run completes from frontend and exposes all major artifacts.
- A real AI + real Notion smoke test works when credentials and Notion schema are configured.
- Frontend shows validation issues, review actions, sync events, and final coverage.
- Backend tests pass.
- Frontend build/lint passes.
- README includes final demo walkthrough.

