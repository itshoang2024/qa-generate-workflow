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

Current implemented endpoints:

| Method | Path | Mutates state | Purpose |
|---|---|---:|---|
| `GET` | `/health` | No | Report app and provider mode. |
| `GET` | `/providers/status` | No | Report AI, Notion, and repository provider readiness. |
| `POST` | `/projects` | Yes | Create a game project. |
| `GET` | `/projects` | No | List game projects for the S0 dropdown. |
| `GET` | `/projects/{project_id}` | No | Get one project. |
| `GET` | `/projects/{project_id}/gdd-documents` | No | List registered GDD versions for one game project. |
| `POST` | `/demo-runs` | Yes | Run the Snake Escape pipeline end to end. |
| `GET` | `/runs` | No | List stored runs. |
| `POST` | `/runs/trigger` | Yes | Accept GDD file reference + project selection, choose `NEW_GAME` or `DELTA`, create `run_id`, initialize session memory. |
| `GET` | `/runs/{run_id}` | No | Get one run. |
| `POST` | `/runs/{run_id}/context` | Yes | Load/register/parse GDD, run actionability filter, create HIL-0 questions, and optionally run DELTA diff. |
| `GET` | `/runs/{run_id}/timeline` | No | Get `StageEvent[]`. |
| `GET` | `/runs/{run_id}/coverage` | No | Get `Run.coverage_report`. |
| `GET` | `/runs/{run_id}/sections` | No | Get parsed `GDDSection[]`. |
| `GET` | `/runs/{run_id}/hil-0/questions` | No | List HIL-0 clarification questions for the run. |
| `GET` | `/runs/{run_id}/hil-0/resolutions` | No | List HIL-0 decisions already made for the run. |
| `POST` | `/runs/{run_id}/hil-0/resolutions` | Yes | Resolve one HIL-0 question with provide-artifact, proceed-with-flag, or skip-section. |
| `GET` | `/runs/{run_id}/features` | No | Get `Feature[]`. |
| `GET` | `/runs/{run_id}/epics` | No | Get `Epic[]`. |
| `GET` | `/runs/{run_id}/stories` | No | Get `Story[]`. |
| `GET` | `/runs/{run_id}/tasks` | No | Get `QATask[]`. |
| `GET` | `/runs/{run_id}/test-cases` | No | Get `TestCase[]`. |
| `GET` | `/runs/{run_id}/validation-issues` | No | Get `ValidationIssue[]`. |
| `GET` | `/runs/{run_id}/sync-events` | No | Get mock Notion `SyncEvent[]`. |
| `GET` | `/runs/{run_id}/agent-runs` | No | Get Agent A/B/C input and output snapshots. |
| `GET` | `/runs/{run_id}/review-decisions` | No | Get HIL review decisions for the run. |
| `GET` | `/runs/{run_id}/review-queues/{hil_tier}` | No | Get HIL-0/1/2/3 review items grouped by reviewer, feature, and epic. |
| `POST` | `/review-decisions` | Yes | Store a review decision and update in-memory target status when applicable. |
| `POST` | `/runs/{run_id}/sync-replay` | Yes | Mark failed sync events as replayed. |

## Remaining Planned Source-Of-Truth Endpoints

These endpoints are not fully implemented yet. They represent the remaining target API needed by Task 1-4.

| Method | Path | Stage | Purpose |
|---|---|---|---|
| `GET` | `/runs/{run_id}/risk-events` | Risk | Inspect Task 4 risk events. |

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
- Follow-up endpoints can inspect sections, features, epics, stories, tasks, test cases, agent runs, validation issues, review decisions, and sync events.
- `Feature`, `QATask`, and `TestCase` payloads include `lane` as `AUTO`, `BATCH`, or `BLOCK`.

Router lane rules:

- `AUTO`: confidence `>= 0.85` and no dedup/cross-cutting flag.
- `BATCH`: confidence is below auto threshold but above the stage batch threshold.
- `BLOCK`: confidence is below batch threshold, or a dedup/cross-cutting flag is set.
- Feature lane uses Task 1 Router A batch threshold `0.60`; task and test-case lanes use Router B/C threshold `0.65`.
- After a human approval, the item `review_status` becomes `APPROVED` and the exposed lane becomes `AUTO`, so the item leaves review queues.

## Review Queues

```http
GET /api/v1/runs/{run_id}/review-queues/HIL-2
```

Supported `{hil_tier}` values are `HIL-0`, `HIL-1`, `HIL-2`, and `HIL-3`. Numeric aliases `0`, `1`, `2`, and `3` are accepted.

Response shape:

```json
{
  "data": {
    "run_id": "run_abc123",
    "hil_tier": "HIL-2",
    "group_by": ["reviewer", "feature_id", "epic_id"],
    "item_count": 2,
    "groups": [
      {
        "group_id": "reviewer:Minh|feature:F-004|epic:E-BOOSTERS",
        "reviewer": "Minh",
        "feature_id": "F-004",
        "epic_id": "E-BOOSTERS",
        "item_count": 1,
        "items": [
          {
            "target_type": "task",
            "target_id": "T-007",
            "title": "Review booster first-introduction overlay flow",
            "reviewer": "Minh",
            "lane": "BATCH",
            "review_status": "NEEDS_REVIEW",
            "feature_id": "F-004",
            "epic_id": "E-BOOSTERS",
            "payload": {}
          }
        ]
      }
    ]
  },
  "meta": {"request_id": "req_..."},
  "error": null
}
```

Queue tier mapping:

- `HIL-0`: open preflight clarification questions.
- `HIL-1`: feature and epic-level items for QA Lead review.
- `HIL-2`: QA task items; `BLOCK` lane goes to QA Lead, `BATCH` lane goes to the assignee.
- `HIL-3`: test case items; `BLOCK` lane goes to QA Lead, `BATCH` lane goes to the related task assignee.

## Provider Status

```http
GET /api/v1/providers/status
```

```json
{
  "data": {
    "ai": {"provider": "mock", "credentials_ready": true},
    "notion": {"provider": "real", "credentials_ready": false},
    "repository": {"provider": "supabase", "credentials_ready": true}
  },
  "meta": {"request_id": "req_..."},
  "error": null
}
```

Mock providers are always credential-ready. Real Notion requires `NOTION_TOKEN`; Supabase repository requires both `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.

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
For `epic` decisions, the in-memory store also applies the same decision to features and stories under that epic so HIL-1 approval can clear an epic-level queue.

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
