# Backend Setup Notes

## Architecture

The backend has three layers:

- API routes in `app/api/v1`
- Pipeline services in `app/services`
- Storage adapters in `app/repositories`

The default repository is in-memory so the prototype can demo without Supabase credentials. Supabase Cloud can be enabled later with `REPOSITORY_PROVIDER=supabase`.

## Conda Environment

Use the project Conda environment:

```powershell
cd D:\Code\SUNS-RISER\qa-generate-workflow
conda env create -f environment.yml
conda activate qa-generator
```

If the environment already exists, refresh packages with:

```powershell
conda activate qa-generator
python -m pip install -r backend\requirements.txt
```

## Demo Pipeline

`POST /api/v1/demo-runs` executes the Phase 1 MVP synchronously:

1. Create a run for the Snake Escape project.
2. Parse the root-level `GDD Sample_Snake Escape.docx`.
3. Classify sections as actionable or skipped.
4. Use mock Agent A to create features.
5. Validate source traceability and confidence.
6. Use mock Agent B to create epics, stories, and QA tasks.
7. Validate tasks and create mock Notion task sync events.
8. Use mock Agent C to create four test cases per task.
9. Validate test-case category coverage and create mock Notion test-case sync events.
10. Store a coverage report on the run.

## Target Stage Boundary

The implemented demo path is intentionally compact. Future backend work must follow the root solution files:

- S0 receives GDD upload + project selection, chooses `NEW_GAME` or `DELTA`, creates `run_id`, and initializes session memory.
- S0 does not parse, hash, version, or persist detailed GDD document metadata.
- S1 loads the raw GDD, registers the GDD document version, parses structure, filters actionability, creates HIL-0 questions, and runs DELTA diff.
- Agent A/B/C real providers must use structured JSON output and schema validation.
- Notion real sync must use Sync-A/B/C with `external_id` idempotency and replay from pipeline state.
- Risk handling must persist flags, retries, HIL escalation, correction records, and kill-switch decisions.

## Supabase

The schema stores pipeline objects directly in normalized tables with JSONB for arrays and snapshots. `external_id` is unique for Notion-like idempotency on epics, stories, tasks, and test cases.

Use service role credentials only on the backend. Do not expose them to the Phase 2 frontend.
