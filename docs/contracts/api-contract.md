# API Contract

## Purpose

This document captures the hand-written API contract for the Phase 1 backend. Swagger is available at runtime, but this file documents behavior, mutation boundaries, and response conventions for humans and coding agents.

Target API behavior is derived from the root source-of-truth solution files. Current implemented endpoints are listed separately from planned endpoints so implementation work does not accidentally claim unbuilt behavior.

API entry point: `backend/app/api/v1/routes.py`.

## Base URL

Local default:

```text
http://127.0.0.1:8000/api/v1
```

The prefix is configured by `API_PREFIX`, defaulting to `/api/v1`.

## Response Envelope

All successful API routes should return:

```json
{
  "data": {},
  "meta": {
    "request_id": "req_..."
  },
  "error": null
}
```

Errors use the same top-level shape:

```json
{
  "data": null,
  "meta": {
    "request_id": "req_..."
  },
  "error": {
    "code": "http_404",
    "message": "Run not found.",
    "details": null
  }
}
```

The envelope is implemented in `backend/app/domain/responses.py`.

## Endpoints

Current MVP endpoints:

| Method | Path | Mutates state | Purpose |
|---|---|---:|---|
| `GET` | `/health` | No | Report app and provider mode. |
| `POST` | `/demo-runs` | Yes | Run the Snake Escape pipeline end to end. |
| `GET` | `/runs` | No | List stored runs. |
| `GET` | `/runs/{run_id}` | No | Get one run. |
| `GET` | `/runs/{run_id}/timeline` | No | Get `StageEvent[]`. |
| `GET` | `/runs/{run_id}/coverage` | No | Get `Run.coverage_report`. |
| `GET` | `/runs/{run_id}/sections` | No | Get parsed `GDDSection[]`. |
| `GET` | `/runs/{run_id}/features` | No | Get `Feature[]`. |
| `GET` | `/runs/{run_id}/tasks` | No | Get `QATask[]`. |
| `GET` | `/runs/{run_id}/test-cases` | No | Get `TestCase[]`. |
| `GET` | `/runs/{run_id}/validation-issues` | No | Get `ValidationIssue[]`. |
| `GET` | `/runs/{run_id}/sync-events` | No | Get mock Notion `SyncEvent[]`. |
| `POST` | `/review-decisions` | Yes | Store a review decision and update in-memory target status when applicable. |
| `POST` | `/runs/{run_id}/sync-replay` | Yes | Mark failed sync events as replayed. |

## Planned Source-Of-Truth Endpoints

These endpoints are not fully implemented yet. They represent the target API needed by Task 1-4.

| Method | Path | Stage | Purpose |
|---|---|---|---|
| `POST` | `/projects` | Setup | Create a game project. |
| `GET` | `/projects` | Setup | List game projects for the S0 dropdown. |
| `GET` | `/projects/{project_id}` | Setup | Get one project. |
| `POST` | `/runs/trigger` | S0 | Accept GDD upload reference + project selection, choose `NEW_GAME` or `DELTA`, create `run_id`, initialize session memory. |
| `POST` | `/runs/{run_id}/context` | S1 | Load/register/parse GDD, run actionability filter, create HIL-0 questions, and optionally run DELTA diff. |
| `GET` | `/projects/{project_id}/gdd-documents` | S1 | List registered GDD versions for one game project. |
| `GET` | `/runs/{run_id}/epics` | S4/HIL-1 | Inspect generated/approved epics. |
| `GET` | `/runs/{run_id}/stories` | S4 | Inspect generated stories. |
| `GET` | `/runs/{run_id}/agent-runs` | Agents | Inspect agent input/output snapshots. |
| `GET` | `/runs/{run_id}/review-decisions` | HIL | Inspect human decisions. |
| `GET` | `/runs/{run_id}/risk-events` | Risk | Inspect Task 4 risk events. |
| `GET` | `/providers/status` | Ops | Show provider readiness and missing credentials. |

S0 response shape should include the Task 1 output inside the envelope:

```json
{
  "data": {
    "run_id": "run_...",
    "project_id": "snake-escape",
    "gdd_file": "upload-or-file-reference",
    "mode": "NEW_GAME"
  },
  "meta": {"request_id": "req_..."},
  "error": null
}
```

S0 must not parse or register detailed GDD document metadata. S1 owns that work.

## Main Demo Request

```http
POST /api/v1/demo-runs
Content-Type: application/json
```

```json
{
  "preset": "snake_escape",
  "mode": "NEW_GAME",
  "auto_approve": true
}
```

Expected result:

- `data.status` is `COMPLETED`.
- `data.current_stage` is `FINAL_COVERAGE`.
- `data.coverage_report` contains feature/task/test-case counts.
- Follow-up endpoints can inspect sections, features, tasks, test cases, validation issues, and sync events.

## Review Decision Request

```http
POST /api/v1/review-decisions
Content-Type: application/json
```

```json
{
  "run_id": "run_abc123",
  "target_type": "task",
  "target_id": "T-007",
  "decision": "APPROVED",
  "reviewer": "Minh",
  "comment": "Looks valid for UI review.",
  "patch": null
}
```

Supported target types in the in-memory repository are:

- `feature`
- `epic`
- `story`
- `task`
- `test_case`

In-memory status updates are best-effort and match either internal `id` or public IDs such as `task_id`.

## Status Codes

| Case | Status |
|---|---:|
| Success | 200 |
| Run not found | 404 |
| Missing GDD path | 404 |
| Unsupported preset | 422 |
| Target stage not implemented | 422 |
| Unexpected exception | 500 |

## Compatibility Rules

- Do not remove the envelope unless all frontend/API consumers are updated.
- New endpoints should live under `/api/v1`.
- Keep route handlers thin; orchestration belongs in services.
- If a route mutates state, document it in this file.
- Do not return raw Supabase client responses from routes.

## Validation Checklist For API Changes

Run:

```powershell
cd D:\Code\SUNS-RISER\qa-generate-workflow
conda activate qa-generator
cd backend
pytest tests/test_api.py
```

Also smoke test Swagger at:

```text
http://127.0.0.1:8000/docs
```
