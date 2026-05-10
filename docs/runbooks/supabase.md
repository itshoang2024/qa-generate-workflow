# Supabase Runbook

## Purpose

Use this runbook to enable cloud persistence through Supabase. The default local demo uses in-memory storage and does not require this setup.

This runbook describes the current MVP schema. The target knowledge-base design also needs future tables such as `gdd_documents`, `session_memory`, `project_memory`, `risk_events`, and `notion_page_mappings`.

## Safety Notes

- Use a Supabase project created for this prototype.
- Use service-role credentials only on the backend.
- Never expose `SUPABASE_SERVICE_ROLE_KEY` to a frontend, browser, or committed file.
- The current schema is intended for prototype data, not production retention.

## Apply The Schema

1. Open the Supabase project SQL editor.
2. Paste and run `supabase/schema.sql`.
3. Confirm the following tables exist:
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

Future source-of-truth tables are not implemented in the current schema yet. Add them only when implementing the matching S1, risk, and Notion Sync-A/B/C behavior.

## Configure The Backend

Set environment variables before starting the server:

```powershell
cd D:\Code\SUNS-RISER\qa-generate-workflow
conda activate qa-generator
$env:REPOSITORY_PROVIDER = "supabase"
$env:SUPABASE_URL = "https://your-project.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"
cd backend
uvicorn app.main:app --reload
```

Optional GDD path:

```powershell
$env:SNAKE_GDD_PATH = "D:\Code\SUNS-RISER\qa-generate-workflow\data\GDD_Sample_Snake Escape.docx"
```

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
| `Supabase storage requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY` | Missing env vars. | Set both variables in the same shell that starts uvicorn. |
| `property/table does not exist` or HTTP 400 from Supabase | Schema was not applied or table names changed. | Re-run `supabase/schema.sql` in a test project. |
| Insert fails on `external_id` uniqueness | Reusing stable fixture external IDs in a table with existing rows. | Use a clean test project or inspect existing rows before rerunning. |
| API works in memory but fails in Supabase | Provider difference or schema mismatch. | Compare `docs/contracts/storage-contract.md` against `supabase/schema.sql`. |

## Recovery

For prototype data, the simplest recovery is:

1. Stop the backend.
2. Clear prototype rows in the Supabase project.
3. Re-run `supabase/schema.sql` if schema drift is suspected.
4. Restart backend and run the demo again.
