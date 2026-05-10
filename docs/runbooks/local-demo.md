# Local Demo Runbook

## Purpose

Use this runbook to start the backend locally, run the Snake Escape demo pipeline, and inspect generated QA workflow artifacts.

This runbook covers the current MVP. The backend now exposes S0 trigger/mode detection separately from S1 GDD context loading, while `/demo-runs` remains the one-call stable mock demo path.

## Prerequisites

- Conda is installed.
- The repository root is `D:\Code\SUNS-RISER\qa-generate-workflow`.
- The `qa-generator` environment exists or can be created from `environment.yml`.

## One-Time Setup

```powershell
cd D:\Code\SUNS-RISER\qa-generate-workflow
conda env create -f environment.yml
```

If the environment already exists:

```powershell
cd D:\Code\SUNS-RISER\qa-generate-workflow
conda activate qa-generator
python -m pip install -r backend\requirements.txt
```

## Environment

Default demo mode does not require `backend/.env`:

```env
AI_PROVIDER=mock
NOTION_PROVIDER=mock
REPOSITORY_PROVIDER=memory
```

For local overrides, copy `backend/.env.example` to `backend/.env`. The backend loads `backend/.env` automatically on startup. Restart `uvicorn` after changing it because settings and repository dependencies are cached while the process is running.

Important path note:

- `app/config.py` reads process environment variables first.
- If a key is not present in the process environment, it reads `backend/.env`.
- If `SNAKE_GDD_PATH` is unset, the backend uses `data/GDD_Sample_Snake_Escape.docx`.
- If you set `SNAKE_GDD_PATH`, use an absolute path or a path relative to the project root such as `data/GDD_Sample_Snake_Escape.docx`.
- The repo data sample is `data/GDD_Sample_Snake_Escape.docx`. If this file is missing, the API returns `GDD file not found` and the path should be fixed explicitly.

Example PowerShell override:

```powershell
$env:SNAKE_GDD_PATH = "D:\Code\SUNS-RISER\qa-generate-workflow\data\GDD_Sample_Snake_Escape.docx"
```

## Start The Server

```powershell
cd D:\Code\SUNS-RISER\qa-generate-workflow
conda activate qa-generator
cd backend
uvicorn app.main:app --reload
```

Expected output includes:

```text
Uvicorn running on http://127.0.0.1:8000
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Run The Demo

In Swagger, run:

```http
POST /api/v1/demo-runs
```

Body:

```json
{
  "preset": "snake_escape",
  "mode": "NEW_GAME",
  "auto_approve": true
}
```

Expected response:

- `data.status` is `COMPLETED`.
- `data.current_stage` is `FINAL_COVERAGE`.
- `data.coverage_report.feature_count` is `8`.
- `data.coverage_report.task_count` is `11`.
- `data.coverage_report.test_case_count` is `44`.

Current limitation: this demo executes the whole mock pipeline in one request. For staged testing, use `/api/v1/runs/trigger` followed by `/api/v1/runs/{run_id}/context`.

## Inspect The Run

Use the returned `run_id`:

```http
GET /api/v1/runs/{run_id}/timeline
GET /api/v1/runs/{run_id}/coverage
GET /api/v1/runs/{run_id}/sections
GET /api/v1/runs/{run_id}/features
GET /api/v1/runs/{run_id}/tasks
GET /api/v1/runs/{run_id}/test-cases
GET /api/v1/runs/{run_id}/validation-issues
GET /api/v1/runs/{run_id}/sync-events
```

## Test And Lint

```powershell
cd D:\Code\SUNS-RISER\qa-generate-workflow
conda activate qa-generator
cd backend
pytest
python -m ruff check .
```

Expected test result:

```text
15 passed
```

## Common Failures

| Symptom | Likely cause | Fix |
|---|---|---|
| `GDD file not found` | Invalid `SNAKE_GDD_PATH` or wrong working directory. | Unset `SNAKE_GDD_PATH` or set it to an absolute path. |
| `Only the 'snake_escape' preset is supported` | Request body uses another preset. | Use `preset: "snake_escape"`. |
| Port 8000 already in use | Another local server is running. | Start uvicorn with `--port 8001` and use that Swagger URL. |
| Runs disappear after restart | Default repository is in-memory. | Use Supabase mode if persistence is needed. |
| `backend/.env` changes do nothing | Server was not restarted, or the same variable is set in the shell. | Restart `uvicorn`; unset the shell variable if you want the file value to win. |

## Stop The Server

Press `Ctrl+C` in the terminal running uvicorn.
