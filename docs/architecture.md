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

The root source-of-truth design files are:

- `Task-1-AI-workflow-design.md`: stage boundaries and HIL flow.
- `Task-2-Agent-prompts-JSON.md`: Agent A/B/C prompts and JSON contracts.
- `Task-3-Sync-to-Notion.md`: Notion workspace, field mapping, Sync-A/B/C, idempotency, retry.
- `Task-4-Risk-Failure-handling.md`: risk taxonomy, failure responses, learning loop, kill switch.

## Runtime Boundaries

| Boundary | Current implementation |
|---|---|
| API runtime | FastAPI app in `backend/app/main.py`. |
| AI agents | Mock outputs generated from `data/snake_escape_fixture.json`. |
| GDD parser | DOCX parser in `backend/app/services/gdd_parser.py`. |
| Validation layer | Deterministic validators in `backend/app/services/validators.py`. |
| Notion sync | Mock payload events in `backend/app/services/notion_sync.py`. |
| Storage | In-memory by default; optional Supabase via `REPOSITORY_PROVIDER=supabase` in `backend/.env`. |
| Frontend | Not implemented; expected to consume `/api/v1` only. |

## Target Stage Boundaries

| Stage | Boundary |
|---|---|
| S0 | Trigger + mode detection only. Input is GDD upload plus project selection. Existing project means `DELTA`; new project means `NEW_GAME`; create `run_id`; initialize session memory. |
| S1 | Context loader. Owns raw GDD loading, GDD version registration, structural parse, actionability filter, HIL-0, and DELTA diff. |
| S2 / S6 | Agent A (GDD Analyzer) and Agent C (Test Case Generator). Must use structured JSON contracts and source-grounding rules from Task 2. |
| S4.1 / S4.2 / S4.3 | Agent B hierarchical decomposition (Phase 1.8). S4.1 is Agent B1 Epic Planner (single call, ~3-5KB input). S4.2 is Agent B2 Story Planner, fan-out per epic with bounded concurrency. S4.3 is Agent B3 Task Planner, fan-out per story. Legacy bundled `S4_AGENT_B` stays for `/demo-runs` smoke compatibility. |
| S3 / S5 / S7 | Deterministic validation and routers. Must enforce schema, traceability, confidence, dedup, assignee, and coverage rules. S5 splits into per-substage validators V-B1 (post S4.1), V-B2 (post each S4.2 fan-out), V-B3 (full plan after S4.3) plus mandatory cross-story / cross-epic dedup. |
| HIL | Human review gates: HIL-0 clarification, HIL-1 feature/epic review (with optional Lead edit at `<EpicReviewPanel>` between S4.1 and S4.2), HIL-2 task review, HIL-3 test-case review. |
| Notion sync | Destination-only sync. Phase 1.8 splits Sync-A into Sync-A1 (epics post S4.1) + Sync-A2 (stories post each S4.2 fan-out). Sync-B (tasks post HIL-2) and Sync-C (test cases post HIL-3) remain. All idempotent via `external_id`. |
| Risk | Stores flags for hallucination, scope drift, JSON format failure, duplicates, bad assignee, Notion sync failure, incomplete GDD, plus Phase 1.8 additions: Agent B sub-stage timeout / partial fan-out failure (7a) and cross-epic / cross-story task duplication (7b). |
| Agent B Job | Phase 1.8 `AgentBJob` artifact tracks per-fan-out job state (`scope_type` ∈ {epic, story}, `scope_id`, `status` ∈ {queued, running, success, failed, timeout}, `attempt_count`, error fields). Persisted in repository so UI's `<AgentBJobBoard>` can poll and manual retry can target individual jobs. |

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

Target artifact flow differs before and around the current demo path:

- S0 creates a run/session from upload + project selection but does not parse the file.
- S1 registers the GDD version and parses/filter sections.
- Sync-A should write Epic/Story after HIL-1 before task sync.
- Sync-B writes Tasks after HIL-2 or auto-approval.
- Sync-C writes Test Cases after HIL-3 or auto-approval.
- Risk events and correction records should be persisted alongside validation issues.

## Data Sources

- `data/GDD_Sample_Snake_Escape.docx`: repo-local sample GDD artifact preferred by default config.
- `data/snake_escape_fixture.json`: deterministic mock agent output.
- `backend/.env.example`: expected backend environment variables.
- `supabase/schema.sql`: optional cloud persistence schema.

Note: `app/config.py` reads process environment variables first, then falls back to `backend/.env`. Restart the backend after changing `backend/.env` because settings and repository dependencies are cached in-process.

## Public Interfaces

- REST API under `/api/v1`; see `docs/contracts/api-contract.md`.
- Pydantic domain models in `backend/app/domain/models.py`.
- Repository interface in `backend/app/repositories/workflow_repository.py`.
- Supabase table schema in `supabase/schema.sql`.
- Mock fixture shape in `docs/fixtures.md`.

## Current Limitations

- The pipeline is synchronous and executes inside the request cycle. Phase 1.8 introduces fan-out concurrency for S4.2 / S4.3 using `asyncio.gather` bounded by `Semaphore`, still inside the same FastAPI request lifecycle (no external job queue yet).
- Only `preset="snake_escape"` is supported by `/demo-runs`.
- `RunMode.DELTA` is modelled and DELTA section diff scaffold exists in S1; downstream DELTA behavior in B1/B2/B3 + Sync-A1/A2 follows Phase 1.8 implementation.
- Notion sync is mock-only. Real Notion adapter pending.
- AI provider selection supports `mock` (default) and `openai` for Agent A and bundled Agent B; Phase 1.8 introduces `openai` Agent B1/B2/B3 with streaming. Agent C real adapter still pending.
- In-memory storage is process-local and resets when the server restarts. Supabase persistence remains optional.
- S0/S1 are split in the backend service and public API; `/demo-runs` remains a synchronous wrapper for the stable mock demo and uses the legacy bundled S4 path for back-compat.
- Phase 1.8 docs are landed; backend + frontend implementation pending.

## Change Impact Notes

- Adding real AI should introduce an adapter with the same Agent A/B/C method boundaries used by `MockAgentClient`.
- Adding real Notion should preserve `SyncEvent` audit records and `external_id` idempotency.
- Adding arbitrary GDD upload will affect parser inputs, API request shape, storage of source documents, and test fixtures.
- Adding a frontend should consume API endpoints only; it should not read Supabase directly.
- When implementing upload, keep S0 as trigger/mode detection and put GDD version registration/parsing in S1.
- When implementing real agents, update JSON contracts, validators, retry policy, and risk docs together.
