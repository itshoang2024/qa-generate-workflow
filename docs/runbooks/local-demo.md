# Local Demo Runbook

## Purpose

Use this runbook to start the backend locally, run the Snake Escape demo pipeline, and inspect generated QA workflow artifacts.

This runbook covers the current MVP. The target workflow in the root solution files splits S0 trigger/mode detection from S1 GDD context loading; that split is not fully implemented yet.

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

Default demo mode does not require `.env`:

```env
AI_PROVIDER=mock
NOTION_PROVIDER=mock
REPOSITORY_PROVIDER=memory
```

Important path note:

- `app/config.py` reads environment variables from the process.
- It does not auto-load `.env`.
- If `SNAKE_GDD_PATH` is unset, the backend falls back to the parent workspace file `..\GDD Sample_Snake Escape.docx`.
- If you set `SNAKE_GDD_PATH`, use a valid path from the process working directory or an absolute path.
- The tracked copy in this repository is `data/GDD_Sample_Snake Escape.docx`.

Example PowerShell override:

```powershell
$env:SNAKE_GDD_PATH = "D:\Code\SUNS-RISER\qa-generate-workflow\data\GDD_Sample_Snake Escape.docx"
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

Current limitation: this demo executes the whole mock pipeline in one request. It does not yet expose the target S0 output `{run_id, project_id, gdd_file, mode}` as a separate trigger step.

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
6 passed
```

## Common Failures

| Symptom | Likely cause | Fix |
|---|---|---|
| `GDD file not found` | Invalid `SNAKE_GDD_PATH` or wrong working directory. | Unset `SNAKE_GDD_PATH` or set it to an absolute path. |
| `Only the 'snake_escape' preset is supported` | Request body uses another preset. | Use `preset: "snake_escape"`. |
| Port 8000 already in use | Another local server is running. | Start uvicorn with `--port 8001` and use that Swagger URL. |
| Runs disappear after restart | Default repository is in-memory. | Use Supabase mode if persistence is needed. |
| `.env` changes do nothing | `.env` is not auto-loaded by code. | Set variables in the shell before starting uvicorn, or add explicit dotenv loading in code. |

## Stop The Server

Press `Ctrl+C` in the terminal running uvicorn.
