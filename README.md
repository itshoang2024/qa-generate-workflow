# QA Generate Workflow Prototype

A FastAPI turns the Snake Escape sample GDD into a QA execution plan with feature inventory, QA tasks, test cases, validation issues, and mock Notion sync payloads.

Live demo: https://qa-generate-workflow.vercel.app/

Phase 1 focuses on backend/API. The frontend can be built later against the documented `/api/v1` endpoints.

The target product behavior is defined by the four root-level solution files in the parent workspace:

- `Task-1-AI-workflow-design.md`
- `Task-2-Agent-prompts-JSON.md`
- `Task-3-Sync-to-Notion.md`
- `Task-4-Risk-Failure-handling.md`

Current backend docs distinguish implemented MVP behavior from that target design.

## What Is Included

- FastAPI backend under `backend/`
- Supabase Cloud schema under `supabase/schema.sql`
- Deterministic Snake Escape mock agent fixture under `data/snake_escape_fixture.json`
- Mock-first AI and Notion adapters
- In-memory repository for zero-setup demo runs
- Optional Supabase repository for cloud persistence
- Unit and API tests

## Source-Of-Truth Stage Boundary

For future implementation work, keep this boundary intact:

- S0 only handles trigger + mode detection from GDD upload and project selection. Existing project means `DELTA`; new project means `NEW_GAME`; S0 creates `run_id` and session memory.
- S1 handles raw GDD loading, document version registration, structural parsing, actionability filtering, HIL-0, and DELTA diff.
- Agent stages must follow the structured JSON contracts in Task 2.
- Notion sync must follow Task 3 Sync-A/B/C and use `external_id` for idempotency.
- Risk handling must follow Task 4 severity, retry, HIL, learning-loop, and kill-switch behavior.

## Quick Start

```powershell
cd D:\Code\SUNS-RISER\qa-generate-workflow
conda env create -f environment.yml
conda activate qa-generator
cd backend
uvicorn app.main:app --reload
```

If the `qa-generator` environment already exists:

```powershell
cd D:\Code\SUNS-RISER\qa-generate-workflow
conda activate qa-generator
python -m pip install -r backend\requirements.txt
cd backend
uvicorn app.main:app --reload
```

Open Swagger:

```text
http://127.0.0.1:8000/docs
```

Run the main demo request:

```http
POST /api/v1/demo-runs
{
  "preset": "snake_escape",
  "mode": "NEW_GAME",
  "auto_approve": true
}
```

Then inspect:

- `GET /api/v1/runs/{run_id}/timeline`
- `GET /api/v1/runs/{run_id}/coverage`
- `GET /api/v1/runs/{run_id}/features`
- `GET /api/v1/runs/{run_id}/tasks`
- `GET /api/v1/runs/{run_id}/test-cases`
- `GET /api/v1/runs/{run_id}/validation-issues`
- `GET /api/v1/runs/{run_id}/sync-events`

## Environment

Copy `backend/.env.example` to `backend/.env` if you want local overrides. The backend loads `backend/.env` automatically when it starts. Restart `uvicorn` after changing this file because settings and repository dependencies are cached during the process lifetime.

Default mode:

```env
AI_PROVIDER=mock
NOTION_PROVIDER=mock
REPOSITORY_PROVIDER=memory
```

To use Supabase Cloud later:

```env
REPOSITORY_PROVIDER=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

Run `supabase/schema.sql` in the Supabase SQL editor before switching the repository provider. Confirm the active provider with `GET /api/v1/health`; it should return `"repository_provider": "supabase"` when Supabase mode is active.

## Test

```powershell
cd D:\Code\SUNS-RISER\qa-generate-workflow
conda activate qa-generator
cd backend
pytest
```

## Documentation

- `PLAN.md` - end-to-end prototype completion plan across backend, integrations, frontend, and submission polish.
- `TASKS.md` - end-to-end milestone checklist with verification criteria.
- `backend/PLAN.md` - backend implementation plan mapped to the Task 1 pipeline stages.
- `backend/TASKS.md` - backend stage checklist with per-task verification steps.
- `AGENTS.md` - coding-agent orientation, safe change rules, and module map.
- `docs/architecture.md` - system boundaries, runtime flow, and current limitations.
- `docs/contracts/api-contract.md` - REST envelope, endpoints, and mutation behavior.
- `docs/contracts/pipeline-contract.md` - stage order, IDs, validation, and coverage shape.
- `docs/contracts/storage-contract.md` - repository and Supabase storage semantics.
- `docs/runbooks/local-demo.md` - local demo setup, Swagger walkthrough, troubleshooting.
- `docs/runbooks/supabase.md` - optional Supabase Cloud setup and recovery notes.
- `docs/fixtures.md` - how to edit deterministic mock agent data safely.

## Phase 2 Frontend Direction

Build a Next.js frontend that consumes only the API:

- Run dashboard and timeline
- GDD section viewer
- Feature review screen
- Task board grouped by assignee
- Test case review screen
- Coverage report
- Mock Notion sync log
