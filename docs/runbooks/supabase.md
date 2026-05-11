# Supabase Runbook

## Purpose

Use this runbook to enable cloud persistence through Supabase. The default local demo uses in-memory storage and does not require this setup.

This runbook describes the current MVP schema. Future risk and sync work will add tables such as `project_memory`, `risk_events`, and `notion_page_mappings`.

## Safety Notes

- Use a Supabase project created for this prototype.
- Use service-role credentials only on the backend.
- Never expose `SUPABASE_SERVICE_ROLE_KEY` to a frontend, browser, or committed file.
- The current schema is intended for prototype data, not production retention.

## Apply The Schema

1. Open the Supabase project SQL editor.
2. Paste and run `supabase/schema.sql`. The script is safe to re-run against an existing prototype project; it includes additive `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` statements for schema upgrades.
3. Confirm the following tables exist:
   - `projects`
   - `runs`
   - `gdd_documents`
   - `gdd_sections`
   - `hil0_questions`
   - `hil0_resolutions`
   - `features`
   - `epics`
   - `stories`
   - `qa_tasks`
   - `test_cases`
   - `validation_issues`
   - `risk_events`
   - `review_decisions`
   - `agent_runs`
   - `sync_events`

## Configure The Backend

Copy the backend env example, then fill in the Supabase values:

```powershell
cd D:\Code\SUNS-RISER\qa-generate-workflow
Copy-Item backend\.env.example backend\.env
```

Set these values in `backend\.env`:

```env
REPOSITORY_PROVIDER=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

Start the server:

```powershell
conda activate qa-generator
cd backend
uvicorn app.main:app --reload
```

Optional GDD path:

```env
SNAKE_GDD_PATH=data/GDD_Sample_Snake_Escape.docx
```

Confirm the backend loaded Supabase mode:

```http
GET /api/v1/health
```

The response should include `"repository_provider": "supabase"`. Restart `uvicorn` after editing `backend\.env`; settings and repository dependencies are cached for the running process.

## Smoke Test

Run:

```http
POST /api/v1/demo-runs
{
  "preset": "snake_escape",
  "mode": "NEW_GAME",
  "auto_approve": true
}
```

Expected API result:

- `data.status` is `COMPLETED`.
- `data.coverage_report.task_count` is `11`.

Expected Supabase rows:

- one row in `projects`
- one row in `runs`
- rows in `gdd_sections`
- eight rows in `features`
- eleven rows in `qa_tasks`
- forty-four rows in `test_cases`
- rows in `validation_issues`
- rows in `risk_events`
- rows in `sync_events`

## Replace Semantics Warning

The Supabase repository uses delete-then-insert behavior for these methods:

- `set_features()`
- `set_epics()`
- `set_stories()`
- `set_tasks()`
- `set_test_cases()`

These methods replace all rows of that type for the run. Do not use them for partial updates unless that replacement behavior is intended.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Supabase storage requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY` | Missing values in `backend/.env` or the server was not restarted. | Fill both values, restart `uvicorn`, then check `/api/v1/health`. |
| `Could not find the 'delta_report' column of 'runs' in the schema cache`, `Could not find the 'cross_cutting_flag' column of 'features' in the schema cache`, missing `risk_events`, or any `PGRST204` missing-column/table error | Supabase table schema is older than the backend models, or PostgREST cache has not reloaded. | Re-run `supabase/schema.sql`; it adds missing columns such as `dedup_flag`, `cross_cutting_flag`, test-case `confidence`, sign-off fields, and `risk_events`, then sends `notify pgrst, 'reload schema';`. Restart the backend and retry the request. |
| `property/table does not exist` or HTTP 400 from Supabase | Schema was not applied or table names changed. | Re-run `supabase/schema.sql` in a test project. |
| `httpcore.RemoteProtocolError: <ConnectionTerminated error_code:1 ...>` during `Load Context` or bulk writes | Supabase/PostgREST closed an HTTP/2 stream during a backend write. The backend Supabase repository now forces its PostgREST client to HTTP/1.1. | Restart the backend so the cached repository is recreated with the HTTP/1.1 client, then retry the UI action. |
| Insert fails on `external_id` uniqueness | Reusing stable fixture external IDs in a table with existing rows. | Use a clean test project or inspect existing rows before rerunning. |
| API works in memory but fails in Supabase | Provider difference or schema mismatch. | Compare `docs/contracts/storage-contract.md` against `supabase/schema.sql`. |

## Recovery

For prototype data, the simplest recovery is:

1. Stop the backend.
2. Clear prototype rows in the Supabase project.
3. Re-run `supabase/schema.sql` if schema drift is suspected.
4. Restart backend and run the demo again.
