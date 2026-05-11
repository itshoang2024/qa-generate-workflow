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
| `POST` | `/runs/{run_id}/agent-a` | Yes | Advance S1 to S3 with Agent A and Validation A. |
| `POST` | `/runs/{run_id}/agent-b` | Yes | (Legacy bundled, used by `/demo-runs`) Advance S3 to S5 with Agent B coverage guard, Validation B, Sync-A, and Sync-B. Phase 1.8 makes this a sequential wrapper around the three substage endpoints below. |
| `POST` | `/runs/{run_id}/agent-b/epics` | Yes | (Phase 1.8) Advance S3 -> S4.1 with Agent B1, V-B1, Sync-A1. Returns generated epics. |
| `POST` | `/runs/{run_id}/agent-b/stories` | Yes | (Phase 1.8) Advance S4.1 -> S4.2 with Agent B2 fan-out per epic, V-B2 per epic, Sync-A2 per epic. Spawns one `AgentBJob{scope=epic}` per epic. |
| `POST` | `/runs/{run_id}/agent-b/tasks` | Yes | (Phase 1.8) Advance S4.2 -> S4.3 with Agent B3 fan-out per story, V-B3 full plan (incl. cross-story/cross-epic dedup), Sync-B. Spawns one `AgentBJob{scope=story}` per story. |
| `POST` | `/runs/{run_id}/agent-b/jobs/{job_id}/retry` | Yes | (Phase 1.8) Retry a single `AgentBJob` that is `FAILED` or `TIMEOUT`. Does not re-fan-out sibling jobs. |
| `GET` | `/runs/{run_id}/agent-b-jobs` | No | (Phase 1.8) List `AgentBJob[]` for the run, ordered by `started_at`. Frontend polls this every 2s during fan-out. |
| `PATCH` | `/runs/{run_id}/epics/{epic_id}` | Yes | (Phase 1.8) Lead edit on `<EpicReviewPanel>` before S4.2. Body: `{title?, description?, feature_ids?}`. Rejected unless `current_stage == S4_1_AGENT_B_EPICS`. |
| `POST` | `/runs/{run_id}/epics/merge` | Yes | (Phase 1.8) Merge ≥2 epics into one. Body: `{source_epic_ids: [...], target_title, target_description}`. Validates feature_id coverage. |
| `POST` | `/runs/{run_id}/epics/split` | Yes | (Phase 1.8) Split one epic into N. Body: `{epic_id, splits: [{title, description, feature_ids}, ...]}`. Every original feature must end up in exactly one new epic. |
| `POST` | `/runs/{run_id}/agent-c` | Yes | Advance S5 to S7 with Agent C, Validation C, and Sync-C. |
| `POST` | `/runs/{run_id}/finalize` | Yes | Build final coverage and mark the run completed. |
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
| `GET` | `/runs/{run_id}/risk-events` | No | Get Task 4 `RiskEvent[]`. |
| `GET` | `/runs/{run_id}/sync-events` | No | Get mock Notion `SyncEvent[]`. |
| `GET` | `/runs/{run_id}/agent-runs` | No | Get Agent A/B/C input and output snapshots. |
| `GET` | `/runs/{run_id}/review-decisions` | No | Get HIL review decisions for the run. |
| `GET` | `/runs/{run_id}/review-queues/{hil_tier}` | No | Get HIL-0/1/2/3 review items grouped by reviewer, feature, and epic. |
| `POST` | `/review-decisions` | Yes | Store a review decision and update in-memory target status when applicable. |
| `POST` | `/runs/{run_id}/hil-2/tasks/{task_id}/decision` | Yes | Store a structured HIL-2 task action and apply controlled task patches such as assignee override. |
| `POST` | `/runs/{run_id}/sync-replay` | Yes | Mark failed sync events as replayed. |
| `POST` | `/runs/{run_id}/sign-off` | Yes | Record QA Lead sign-off and surface it in run coverage. |

## Remaining Planned Source-Of-Truth Endpoints

No planned read endpoint remains in this section for the current slice. Future slices may add write surfaces for learning-loop corrections and real provider operations.

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
- `sync-events` payloads include `sync_phase` as `Sync-A`, `Sync-B`, or `Sync-C`.
- `risk-events` contains deterministic Task 4 escalations derived from validation issue codes.
- `Feature`, `QATask`, and `TestCase` payloads include `lane` as `AUTO`, `BATCH`, or `BLOCK`.

Router lane rules:

- `AUTO`: confidence `>= 0.85` and no dedup/cross-cutting flag.
- `BATCH`: confidence is below auto threshold but above the stage batch threshold.
- `BLOCK`: confidence is below batch threshold, or a dedup/cross-cutting flag is set.
- Feature lane uses Task 1 Router A batch threshold `0.60`; task and test-case lanes use Router B/C threshold `0.65`.
- After a human approval, the item `review_status` becomes `APPROVED` and the exposed lane becomes `AUTO`, so the item leaves review queues.

## Stage Endpoint Errors

Per-stage endpoints return HTTP 409 with the standard error envelope for blocked workflow advances. Common `error.code` values:

- `wrong_stage`: the run is not at the expected stage.
- `hil_gate_blocked`: the prior HIL queue still has `NEEDS_REVIEW` or `BLOCKED` items.
- `kill_switch_tripped`: critical risk threshold halted downstream generation.
- `agent_b_coverage_exhausted`: (legacy bundled S4) Agent B still omitted approved HIL-1 feature or epic coverage after bounded retry; Sync-A/B was not executed.

Phase 1.8 additions:

- `agent_b_substage_partial_failure`: `/agent-b/stories` or `/agent-b/tasks` finished with one or more `AgentBJob` in `FAILED` / `TIMEOUT`. `error.details.failed_jobs` lists `{job_id, scope_type, scope_id, error_code}`. Recovery path: call `/agent-b/jobs/{id}/retry` for each, then re-invoke the substage endpoint or rely on automatic stage advance once all jobs are terminal-success.
- `epic_edit_after_lock`: `PATCH /epics/{id}` or merge/split called when `current_stage != S4_1_AGENT_B_EPICS`. `error.details.current_stage` carries the actual stage.
- `epic_edit_feature_coverage`: merge or split body fails the exhaustive feature coverage check. `error.details.unassigned_features` lists feature_ids not placed anywhere; `error.details.duplicated_features` lists feature_ids placed in more than one target epic.

For `agent_b_coverage_exhausted`, `error.details.issues` includes `missing_agent_b_feature_coverage`, `missing_agent_b_epic_coverage`, and the final exhaustion issue.

## Phase 1.8 — Agent B Substage Endpoints

### Run Agent B1 (S4.1 — Epic Planner)

```http
POST /api/v1/runs/{run_id}/agent-b/epics
Content-Type: application/json
```

Body: empty `{}` (S4.1 reads HIL-1 context from `Run.session_memory`).

Successful response:

```json
{
  "data": {
    "run_id": "run_abc123",
    "current_stage": "S4_1_AGENT_B_EPICS",
    "epics": [
      {
        "epic_id": "E-CORE-GAMEPLAY",
        "title": "Core Gameplay",
        "description": "Tap-to-move mechanics, health system, level fail/win flow.",
        "feature_ids": ["F-001", "F-002", "F-003"],
        "rationale": "These features form the single-touch loop core to every level interaction.",
        "external_id": "snake-escape-E-CORE-GAMEPLAY"
      }
    ],
    "sync_a1_event_count": 1
  },
  "meta": {"request_id": "req_..."},
  "error": null
}
```

### Run Agent B2 (S4.2 — Story Planner fan-out)

```http
POST /api/v1/runs/{run_id}/agent-b/stories
Content-Type: application/json
```

Body: empty `{}`. Backend reads current epic state (possibly Lead-edited) from repository.

Successful response (returned after all fan-out jobs reach terminal state):

```json
{
  "data": {
    "run_id": "run_abc123",
    "current_stage": "S4_2_AGENT_B_STORIES",
    "stories_by_epic": {
      "E-CORE-GAMEPLAY": [/* AgentBStorySkeleton[] */],
      "E-BOOSTERS": [/* AgentBStorySkeleton[] */]
    },
    "job_summary": {
      "total": 5,
      "success": 5,
      "failed": 0,
      "timeout": 0
    },
    "sync_a2_event_count": 5
  },
  "meta": {"request_id": "req_..."},
  "error": null
}
```

On partial failure (HTTP 409 with `error.code = "agent_b_substage_partial_failure"`):

```json
{
  "data": null,
  "meta": {"request_id": "req_..."},
  "error": {
    "code": "agent_b_substage_partial_failure",
    "message": "Agent B2 fan-out completed with 1 failed job(s). Retry the failed jobs and re-invoke this endpoint, or call /agent-b/jobs/{id}/retry individually.",
    "details": {
      "failed_jobs": [
        {"job_id": "abjob_xyz", "scope_type": "epic", "scope_id": "E-BOOSTERS", "error_code": "ReadTimeout"}
      ]
    }
  }
}
```

### Run Agent B3 (S4.3 — Task Planner fan-out)

```http
POST /api/v1/runs/{run_id}/agent-b/tasks
Content-Type: application/json
```

Body: empty `{}`. Shape mirrors `/agent-b/stories`; partial failure follows the same envelope.

### Agent B Job Board

```http
GET /api/v1/runs/{run_id}/agent-b-jobs
```

```json
{
  "data": [
    {
      "id": "abjob_xyz",
      "run_id": "run_abc123",
      "scope_type": "epic",
      "scope_id": "E-BOOSTERS",
      "status": "FAILED",
      "attempt_count": 2,
      "error_code": "ReadTimeout",
      "error_message": "OpenAI Agent B2 request timed out after 120s.",
      "started_at": "2026-05-12T10:00:00Z",
      "finished_at": "2026-05-12T10:02:00Z",
      "output_summary": {}
    }
  ],
  "meta": {"request_id": "req_..."},
  "error": null
}
```

### Retry a single Agent B job

```http
POST /api/v1/runs/{run_id}/agent-b/jobs/{job_id}/retry
Content-Type: application/json
```

Body: empty `{}`. Only jobs in `FAILED` or `TIMEOUT` are retryable. Returns the updated `AgentBJob`.

### Edit epic before S4.2

```http
PATCH /api/v1/runs/{run_id}/epics/{epic_id}
Content-Type: application/json
```

```json
{
  "title": "Core Loop & Health",
  "description": "Updated description after Lead review.",
  "feature_ids": ["F-001", "F-002"]
}
```

Returns the patched epic. Rejected with 409 `epic_edit_after_lock` unless `current_stage == S4_1_AGENT_B_EPICS`.

### Merge epics

```http
POST /api/v1/runs/{run_id}/epics/merge
Content-Type: application/json
```

```json
{
  "source_epic_ids": ["E-BOOSTERS", "E-POWERUPS"],
  "target_title": "Boosters & Powerups",
  "target_description": "Combined booster and powerup features."
}
```

Returns the new merged epic. Source epics are deleted; their feature_ids transfer to the target.

### Split epic

```http
POST /api/v1/runs/{run_id}/epics/split
Content-Type: application/json
```

```json
{
  "epic_id": "E-CORE-GAMEPLAY",
  "splits": [
    {"title": "Tap Mechanics", "description": "...", "feature_ids": ["F-001", "F-002"]},
    {"title": "Health & Fail Flow", "description": "...", "feature_ids": ["F-003"]}
  ]
}
```

Source epic is deleted. Every original feature_id must appear in exactly one split (validated server-side; rejected with 409 `epic_edit_feature_coverage` otherwise).

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

## Risk Events

```http
GET /api/v1/runs/{run_id}/risk-events
```

Risk events are derived from deterministic validation issues. Current mappings:

- `missing_source_section`, `task_missing_source_section`, `test_case_missing_source_section` -> S1 hallucination/traceability risk.
- `uncovered_actionable_section` -> S2 scope-drift risk.
- `invalid_assignee` -> S2 assignee mismatch risk.
- `duplicate_task_candidate` -> S2 duplicate-task risk.

## Sign-Off

```http
POST /api/v1/runs/{run_id}/sign-off
Content-Type: application/json
```

```json
{
  "reviewer": "QA Lead"
}
```

The endpoint updates `Run.signed_off_by`, `Run.signed_off_at`, and `Run.coverage_report.sign_off`.

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

Repository status updates are best-effort and match either internal `id` or public IDs such as `task_id`.
For `epic` decisions, the repository also applies the same decision to features and stories under that epic so HIL-1 approval can clear an epic-level queue.
For task decisions, a flat `patch` or nested `patch.task` can update controlled task fields such as `title`, `description`, `assignee`, `priority`, `estimate`, `source_sections`, `status`, `confidence`, `dedup_flag`, and `cross_cutting_flag`.

## HIL-2 Task Decision Request

```http
POST /api/v1/runs/{run_id}/hil-2/tasks/{task_id}/decision
Content-Type: application/json
```

```json
{
  "action": "override_assignee",
  "reviewer": "QA Lead",
  "assignee": "Quan",
  "comment": "Backend telemetry owns this review now."
}
```

Supported actions:

- `approve` -> stores `ReviewDecision.decision=APPROVED`; optional `patch` applies inline task edits before approval.
- `request_edit` -> stores `ReviewDecision.decision=BLOCKED`; optional `patch` is saved under `requested_changes` and does not mutate the task yet.
- `reject` -> stores `ReviewDecision.decision=REJECTED`.
- `override_assignee` -> stores `ReviewDecision.decision=NEEDS_REVIEW`, validates the assignee against the seeded QA roster, applies the task assignee patch, and moves the HIL-2 queue item to the new reviewer when the task remains in a batch lane.

Response shape:

```json
{
  "data": {
    "decision": {},
    "task": {}
  },
  "meta": {"request_id": "req_..."},
  "error": null
}
```

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
