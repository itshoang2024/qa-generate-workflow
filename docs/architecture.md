# Architecture

## System Purpose

`qa-generate-workflow` is a Phase 1 backend prototype for an AI-assisted QA planning workflow. It converts the Snake Escape GDD into:

- parsed GDD sections
- normalized feature inventory
- epics, stories, and QA tasks
- test cases
- validation issues
- mock Notion sync events
- a coverage report

The system is designed to demonstrate workflow thinking, interface boundaries, validation gates, and future frontend readiness. It is not a production AI or Notion integration yet.

## Runtime Boundaries

| Boundary | Current implementation |
|---|---|
| API runtime | FastAPI app in `backend/app/main.py`. |
| AI agents | Mock outputs generated from `data/snake_escape_fixture.json`. |
| GDD parser | DOCX parser in `backend/app/services/gdd_parser.py`. |
| Validation layer | Deterministic validators in `backend/app/services/validators.py`. |
| Notion sync | Mock payload events in `backend/app/services/notion_sync.py`. |
| Storage | In-memory by default; optional Supabase via `REPOSITORY_PROVIDER=supabase`. |
| Frontend | Not implemented; expected to consume `/api/v1` only. |

## Module Boundaries

```text
HTTP client / Swagger
        |
        v
backend/app/main.py
        |
        v
backend/app/api/v1/routes.py
        |
        v
backend/app/services/pipeline.py
        |
        +--> gdd_parser.py
        +--> mock_agents.py
        +--> validators.py
        +--> notion_sync.py
        |
        v
WorkflowRepository interface
        |
        +--> InMemoryWorkflowRepository
        +--> SupabaseWorkflowRepository
```

The API layer should stay thin. Pipeline behavior belongs in `PipelineService`. Storage behavior belongs behind `WorkflowRepository`.

## Artifact Flow

1. `POST /api/v1/demo-runs` creates a `Run` for the `snake-escape` project.
2. `parse_docx_gdd()` reads the configured Snake GDD path and creates `GDDSection` records.
3. `MockAgentClient.analyze_gdd()` creates `Feature` records from fixture data.
4. `validate_features()` emits `ValidationIssue` records for traceability, low confidence, uncovered sections, and pre-flight notes.
5. `MockAgentClient.plan_qa_tasks()` creates `Epic`, `Story`, and `QATask` records.
6. `validate_tasks()` checks feature references, source sections, assignees, confidence, and duplicate candidates.
7. `MockNotionSyncClient` creates mock upsert `SyncEvent` records for epics, stories, and tasks.
8. `MockAgentClient.generate_test_cases()` creates four test cases per QA task.
9. `validate_test_cases()` checks task links, source sections, and category coverage.
10. Mock test-case sync events are stored.
11. `PipelineService._coverage_report()` stores final run coverage.

## Data Sources

- `data/GDD_Sample_Snake Escape.docx`: tracked sample GDD artifact.
- `data/snake_escape_fixture.json`: deterministic mock agent output.
- `.env.example`: expected environment variables.
- `supabase/schema.sql`: optional cloud persistence schema.

Note: `app/config.py` reads environment variables from the process. It does not load `.env` files by itself.

## Public Interfaces

- REST API under `/api/v1`; see `docs/contracts/api-contract.md`.
- Pydantic domain models in `backend/app/domain/models.py`.
- Repository interface in `backend/app/repositories/workflow_repository.py`.
- Supabase table schema in `supabase/schema.sql`.
- Mock fixture shape in `docs/fixtures.md`.

## Current Limitations

- The pipeline is synchronous and executes inside the request cycle.
- Only `preset="snake_escape"` is supported.
- `RunMode.DELTA` exists in the model but no delta diff path is implemented.
- `auto_approve` is accepted by `DemoRunRequest` but currently does not branch behavior.
- Notion sync is mock-only.
- AI provider selection is documented as mock-first; real provider adapters are not implemented.
- In-memory storage is process-local and resets when the server restarts.

## Change Impact Notes

- Adding real AI should introduce an adapter with the same Agent A/B/C method boundaries used by `MockAgentClient`.
- Adding real Notion should preserve `SyncEvent` audit records and `external_id` idempotency.
- Adding arbitrary GDD upload will affect parser inputs, API request shape, storage of source documents, and test fixtures.
- Adding a frontend should consume API endpoints only; it should not read Supabase directly.

