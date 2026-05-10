# Storage Contract

## Purpose

This document defines the storage boundary for the prototype. Both in-memory and Supabase implementations must satisfy `WorkflowRepository` from `backend/app/repositories/workflow_repository.py`.

## Implementations

| Provider | Class | Enabled by |
|---|---|---|
| `memory` | `InMemoryWorkflowRepository` | `REPOSITORY_PROVIDER=memory` or default |
| `supabase` | `SupabaseWorkflowRepository` | `REPOSITORY_PROVIDER=supabase` with Supabase env vars |

Repository construction happens in `backend/app/repositories/factory.py`.

## Repository Responsibilities

The repository layer stores and retrieves already-validated domain models. It should not:

- parse GDD files
- generate AI output
- validate business rules
- construct Notion payloads
- expose storage-provider-specific response objects to API routes

## Required Method Semantics

| Method group | Expected behavior |
|---|---|
| `upsert_project()` | Create or replace a project by `id`. |
| `create_run()` | Store a new run. |
| `update_run()` | Replace run fields and refresh `updated_at`. |
| `list_runs()` | Return latest runs first. |
| `get_run()` | Return `None` when missing. |
| `add_sections()` | Store parsed sections for a run. Current memory behavior replaces the section list. |
| `set_features()` | Replace all features for a run. |
| `set_epics()` | Replace all epics for a run. |
| `set_stories()` | Replace all stories for a run. |
| `set_tasks()` | Replace all tasks for a run. |
| `set_test_cases()` | Replace all test cases for a run. |
| `add_validation_issues()` | Append validation issues. |
| `add_review_decision()` | Append a decision; memory implementation also updates target review status. |
| `add_agent_run()` | Append an agent snapshot. |
| `add_sync_events()` | Append sync event audit records. |
| `replay_failed_sync_events()` | Mark failed sync events as replayed and increment retry count. |

Supabase `set_*` methods delete run rows for that table before inserting replacements. Do not call them with partial collections unless replacement is intended.

## Supabase Tables

Schema file: `supabase/schema.sql`.

Tables:

- `projects`
- `runs`
- `gdd_sections`
- `features`
- `epics`
- `stories`
- `qa_tasks`
- `test_cases`
- `validation_issues`
- `review_decisions`
- `agent_runs`
- `sync_events`

JSON arrays and snapshots are stored as `jsonb`. Timestamps use `timestamptz`.

## Idempotency Keys

These tables enforce unique `external_id`:

- `epics`
- `stories`
- `qa_tasks`
- `test_cases`

`external_id` is the Notion-style idempotency key. It should stay stable across sync replays and future external integrations.

`sync_events.external_id` is not unique because the same external target may produce multiple sync attempts over time.

## Provider Differences

| Behavior | Memory | Supabase |
|---|---|---|
| Persistence | Process-local only | Cloud persistence |
| Review status side effect | Updates target object in memory | Stores decision only |
| Replace behavior | Replaces in Python dict | Deletes matching run rows then inserts |
| Credentials | None | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` |
| Schema required | No | Yes, `supabase/schema.sql` |

The review-status side effect is currently not equivalent across providers. If frontend behavior relies on it, align the Supabase implementation first.

## Environment Variables

```env
REPOSITORY_PROVIDER=memory
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
```

Use `REPOSITORY_PROVIDER=supabase` only after applying `supabase/schema.sql`.

## Compatibility Risks

- Renaming model fields requires schema, repository, fixture, and docs updates.
- Changing `set_*` methods from replacement to merge semantics affects pipeline reruns and Supabase behavior.
- Changing `external_id` formats can break idempotent sync assumptions.
- Exposing Supabase directly to frontend would bypass backend validation and service-role safety.

## Validation Checklist For Storage Changes

Run default tests:

```powershell
cd D:\Code\SUNS-RISER\qa-generate-workflow
conda activate qa-generator
cd backend
pytest
```

For Supabase changes, also manually verify:

1. Apply `supabase/schema.sql` in a test Supabase project.
2. Set `REPOSITORY_PROVIDER=supabase`.
3. Run `POST /api/v1/demo-runs`.
4. Confirm rows exist in `runs`, `features`, `qa_tasks`, `test_cases`, and `sync_events`.

