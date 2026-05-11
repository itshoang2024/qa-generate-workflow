# Backend Completion Plan

## Goal

Complete the backend according to the four source-of-truth solution files in the workspace root:

- `Task-1-AI-workflow-design.md`
- `Task-2-Agent-prompts-JSON.md`
- `Task-3-Sync-to-Notion.md`
- `Task-4-Risk-Failure-handling.md`

The backend must remain mock-first for the local demo while evolving toward the full staged workflow: S0 trigger/mode detection, S1 rule-based context loading, Agent A/B/C structured JSON output, validation routers, HIL gates, Notion Sync-A/B/C, risk handling, and final coverage/sign-off.

## Current Backend State (2026-05-12 - Phase 1.8 docs landed)

> **Phase 1.8 (Agent B Hierarchical Decomposition) docs pass complete; implementation pending.** The real-provider regression on `run_fc5f488fe767` showed Agent B `/v1/responses` calls consistently `ReadTimeout` at 60s and 180s with 25 approved features + 6 HIL-1 epic candidates. Root cause is output-token volume × strict-JSON constraint search latency for the bundled Epic→Story→Task tree. The Phase 1.6 coverage guard correctly traps the resulting partial mock fallback, but the underlying real-provider path is unusable for non-trivial games. Phase 1.8 splits Agent B into three sub-agents (B1 Epic Planner, B2 Story Planner fan-out per epic, B3 Task Planner fan-out per story), introduces an `AgentBJob` model for per-job progress, adds new `/agent-b/epics`, `/agent-b/stories`, `/agent-b/tasks` endpoints (plus `/agent-b-jobs` and epic CRUD endpoints for `<EpicReviewPanel>`), and splits Sync-A into Sync-A1 + Sync-A2.

## Current Backend State (2026-05-11)

- FastAPI app, versioned routes, domain models, repository abstraction (in-memory + Supabase), Snake Escape fixture, Supabase schema, runbooks, and backend tests are in place.
- Per-stage API endpoints are implemented for the stepped UI: `POST /api/v1/runs/{run_id}/agent-a`, `/agent-b`, `/agent-c`, and `/finalize`. Each endpoint enforces stage preconditions and the relevant blocking HIL gate.
- HIL-0 supports both single-question resolution and bulk resolution through `POST /api/v1/runs/{run_id}/hil-0/resolutions/bulk`, which is the dashboard path for "Proceed with flag (n)".
- `POST /api/v1/demo-runs` runs the seeded Snake Escape flow and produces sections, features, epics, stories, tasks, test cases, validation issues, risk events, agent runs, Sync-A/B/C events, coverage, sign-off state, and timeline. Demo counts remain 8 features / 5 epics / 5 stories / 11 tasks / 44 test cases in mock mode.
- `_stage_s0_trigger` and `_stage_s1_context_loader` are split. S0 only creates a run + initializes `session_memory`; S1 owns raw load, `GDDDocument` versioning (`v1`, `v2`, ...), structural parse, QA-actionability filter, HIL-0 question batching, and DELTA section diff (`NEW`/`MODIFIED`/`UNCHANGED`/`REMOVED`).
- `AgentClient` abstract base is implemented with `MockAgentClient` as the default. Agent A and Agent B now have Task 2 structured JSON contracts and OpenAI Responses API adapters behind `AI_PROVIDER=openai`/`real`; Agent C remains mock-backed until its real contract ships.
- S3 Validation A now retries Agent A schema failures, source traceability failures, and uncovered-section reruns up to 3 attempts. Attempt logs are stored in the AgentRun output snapshot and `Run.session_memory`; exhausted retries emit `agent_a_retry_exhausted` and route the final output to HIL-1 instead of silently proceeding.
- HIL-1 now snapshots approved feature IDs, held/review-queue feature IDs, approved feature details, and deterministic epic candidates into `Run.session_memory["hil_1"]`; Agent B receives that snapshot through `plan_qa_tasks(..., hil_context=...)` instead of reading raw Agent A output.
- Closed S4/S5 gap: real Agent B output can no longer omit approved HIL-1 features / epic candidates and proceed to sync. In `run_1cefe76fe58c`, Agent B returned only `Gameplay Logic Scope`; Validation B now catches that partial coverage, retries with feedback, and blocks Sync-A/B when retries are exhausted.
- Router lanes ship end-to-end: `derive_router_lane` thresholds in `domain/models.py`, applied by `validate_*_with_routing`, exposed as computed `Feature.lane` / `QATask.lane` / `TestCase.lane`, and surfaced via `GET /api/v1/runs/{run_id}/review-queues/{HIL-tier}`. `ReviewDecision` cascades epic -> features + stories.
- `NotionSyncClient` abstract base and `MockNotionSyncClient` are implemented. Sync-A writes epics/stories, Sync-B writes eligible tasks with mock page-id relations, and Sync-C writes eligible test cases and transitions synced parent tasks to `Test Cases Ready`.
- Risk events, kill switch, reviewer sign-off, and the extended coverage report (`risk_summary`, `sync_summary`, `gdd_version_metadata`, `sign_off`) are implemented. Learning-loop correction memory is still open.
- Frontend is scaffolded and wired to the staged backend flow. Remaining frontend work is mostly deep-link review/sync/risk/sign-off pages and submission screenshots.

## Stage-Based Plan

### S0 Trigger + Mode Detection

S0 is rule-based and intentionally small.

Source-of-truth behavior:

- Input: GDD upload plus project selection.
- If the user selects an existing project from the dropdown, set `mode=DELTA`.
- If the user creates a new project, set `mode=NEW_GAME`.
- Create a new `run_id`.
- Initialize session memory.
- Output `{run_id, project_id, gdd_file, mode}`.

S0 must not:

- parse the GDD
- hash the file
- persist detailed GDD document metadata
- generate `version_id`
- run DELTA diff
- call AI
- sync to Notion

Those responsibilities start in S1 or later.

Backend outputs:

- `Run`
- `project_id`
- uploaded/raw `gdd_file` reference
- `mode`
- initialized session memory pointer/record
- `StageEvent` for S0

Acceptance:

- New project selection creates a run with `mode=NEW_GAME`.
- Existing project selection creates a run with `mode=DELTA`.
- Response includes `{run_id, project_id, gdd_file, mode}` inside the API envelope.
- `/demo-runs` remains backward-compatible for the mock Snake Escape demo.

### S1 Context Loader

S1 is rule-based and owns GDD raw loading, versioning, structural context, HIL-0, and DELTA diff.

#### S1.1 Structural Parse

Target behavior:

- Load the raw GDD file handed off by S0.
- Register a `GDDDocument` knowledge-base record for the project.
- Auto-generate `version_id` per project as `v1`, `v2`, `v3`, and so on.
- Store optional `description`, `description_status`, `parent_document_id`, filename/path metadata, origin, size, content type, and `sha256`.
- Parse markdown/docx structure: section hierarchy, heading levels, tables, and IMPORTANT/NOTE/TIP blocks.
- Extract game overview fields by fixed template.
- Output `gdd_tree` with `section_id`, `parent_id`, `text`, `tables`, and `flags`.

Acceptance:

- Uploading the first GDD for a project creates `version_id=v1`.
- Uploading the second GDD for the same project creates `version_id=v2`.
- Parser tests prove headings, tables, special blocks, and stable section order are extracted.

#### S1.2 QA-Actionability Filter

Target behavior:

- Mark each section as QA-actionable using deterministic heuristics.
- External-reference-only sections become `actionable=false, reason=external_dep`.
- Metadata sections such as Game Overview and Scope Summary become `actionable=false, reason=metadata`.
- Behavior/UI/data sections become `actionable=true`.
- Non-actionable sections are flagged and excluded from main agent analysis.

Acceptance:

- Feature generation receives only traceable, relevant context.
- Non-actionable content does not create noisy QA tasks.

#### S1.3 HIL-0 Preflight Clarification

Target behavior:

- Detect missing artifacts from IMPORTANT/NOTE/TIP blocks.
- Detect ambiguous thin sections and dangling references.
- Batch all clarification questions into one review screen.
- Support user choices: provide artifact, proceed-with-flag, or skip section.

Acceptance:

- Frontend can show one HIL-0 question batch before Agent A.
- Proceed-with-flag caps confidence and marks incomplete source.
- Skipped sections appear in final coverage.
- Bulk proceed-with-flag resolves the open HIL-0 batch in one API request and avoids parallel Supabase writes from the dashboard.

#### S1.4 DELTA Diff

Target behavior:

- Run only when S0 set `mode=DELTA`.
- Load previous GDD version from long-term memory.
- Compare sections as `NEW`, `MODIFIED`, `UNCHANGED`, or `REMOVED`.
- Load existing Notion tasks for the game.
- Output `delta_report`.

Acceptance:

- Later Agent A/B inputs include `delta_report`.
- `GDDDocument.parent_document_id` links the current version to the compared prior version.

### S2 Agent A - GDD Analyzer

Target behavior from Task 2:

- Input: `actionable_sections`, `user_clarifications`, and `delta_report` when DELTA.
- Output strict JSON with `features`, `coverage_report`, and `ambiguities`.
- Every feature must cite `source_sections`.
- Feature types include gameplay, UI, level, economy, backend/liveops, animation, tutorial, and cross-cutting.
- Agent uses low temperature and structured output where provider supports it.

Acceptance:

- Mock output remains stable.
- Real output validates against schema before persistence.
- Hallucinated or weakly grounded output never bypasses validation.

### Per-Stage Endpoint Orchestration

The backend now exposes the same stage blocks that the UI drives from `<NextStagePanel>`.

Implemented endpoints:

- `POST /api/v1/runs/{run_id}/agent-a`: S1 -> S3, runs Agent A and Validation A.
- `POST /api/v1/runs/{run_id}/agent-b`: S3 -> S5, requires HIL-1 queue clear, runs Agent B, Validation B, Sync-A, and Sync-B.
- `POST /api/v1/runs/{run_id}/agent-c`: S5 -> S7, requires HIL-2 queue clear, runs Agent C, Validation C, and Sync-C.
- `POST /api/v1/runs/{run_id}/finalize`: S7 -> `FINAL_COVERAGE`, requires HIL-3 queue clear and marks the run completed.

Acceptance:

- Wrong-stage calls return HTTP 409 with `error.code="wrong_stage"`.
- HIL-blocked calls return HTTP 409 with `error.code="hil_gate_blocked"` and the offending tier/count in `error.details`.
- `/demo-runs` remains the batch smoke-test route and calls the same stage helpers with `auto_approve=True`.

### S3 Validation A + Router A

Target behavior:

- Validate schema, source traceability, keyword overlap, coverage, and confidence.
- Retry schema/traceability failures up to policy limits.
- Re-run Agent A for uncovered sections when useful.
- Route by final confidence:
  - `>=0.85` auto-proceed
  - `[0.6, 0.85)` HIL-1 batch
  - `<0.6` block/HIL-1

Acceptance:

- Validation issues include stable codes and severity.
- Router lanes are visible to frontend.

### HIL-1 Epic-Level Review

Target behavior:

- QA Lead reviews feature inventory, epic candidates, coverage map, low-confidence items, and split/merge suggestions.
- Lead can approve all, edit item, change assignee, merge/split epic, skip due to insufficient info, or request Agent A rerun with feedback.
- Approved feature list and epic structure are saved to short-term memory.

Acceptance:

- Agent B consumes only approved/corrected features and epic structure.

### S4 Agent B - QA Planner (legacy bundled + Phase 1.8 hierarchical)

> **Phase 1.8 supersedes the bundled S4 behavior for real provider.** The bundled `_stage_s4_agent_b` remains in `pipeline.py` to support `/demo-runs` smoke test and `MockAgentClient.plan_qa_tasks()`. Real provider invocations go through three new sub-stages with their own AgentClient methods and pipeline helpers. See Phase 1.8 section below for the target. The text in this section describes the legacy bundled contract.



Target behavior from Task 2:

- Input: approved features, epic grouping, and per-game memory.
- Output Epic -> Story -> Task tree.
- Every approved HIL-1 feature must appear in at least one story/task, unless Agent B returns an explicit skip reason accepted by Validation B.
- Every HIL-1 epic candidate should be represented by an output epic, unless explicitly skipped with evidence.
- Assignee is rule-based from KB mapping, not invented by AI.
- `external_id` uses stable project/feature/task pattern.
- DELTA behavior:
  - unchanged features skip
  - modified features create update/retest tasks linked by external_id
  - new features create new tasks
  - removed features create archive tasks for Lead confirmation

Acceptance:

- Task output validates against JSON schema and Pydantic models.
- Invalid assignees and duplicate tasks are caught before sync.
- Partial plans from the real provider trigger coverage feedback and bounded retry before any artifacts are persisted or synced.

### Phase 1.8 - Agent B Hierarchical Decomposition (planning)

This is the target architecture for Agent B going forward. Implementation tasks live in `backend/TASKS.md` under "Phase 1.8".

**New domain stages** (additions to `PipelineStage` enum in `app/domain/models.py`):

- `S4_1_AGENT_B_EPICS`
- `S4_2_AGENT_B_STORIES`
- `S4_3_AGENT_B_TASKS`

Legacy `S4_AGENT_B` and `S5_VALIDATION_B_SYNC` remain for the bundled `/demo-runs` path. The stepped UI advances through the three new stages; `/demo-runs` keeps using the legacy stage transitions so its snake-escape counts (8/5/5/11/44) stay exactly stable.

**New domain model**: `AgentBJob`

```python
class AgentBScope(StrEnum):
    EPIC = "epic"
    STORY = "story"

class AgentBJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"

class AgentBJob(BaseModel):
    id: str
    run_id: str
    scope_type: AgentBScope
    scope_id: str          # epic_id for B2 jobs, story_id for B3 jobs
    status: AgentBJobStatus
    attempt_count: int
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    output_summary: dict[str, Any] = Field(default_factory=dict)
```

Repository surface: `add_agent_b_jobs`, `update_agent_b_job`, `list_agent_b_jobs(run_id)`, plus Supabase `agent_b_jobs` table mirroring the model.

**New AgentClient methods** (in `app/services/agents/__init__.py`):

```python
class AgentClient(ABC):
    # Existing methods unchanged.
    @abstractmethod
    def plan_qa_tasks(self, run_id: str, *, hil_context: dict | None = None) -> dict: ...

    # New Phase 1.8 methods:
    @abstractmethod
    def plan_epics(self, run_id: str, *, hil_context: dict) -> dict:
        """Return {'epics': [AgentBEpicSkeleton]} for S4.1."""

    @abstractmethod
    def plan_stories(self, run_id: str, *, epic: dict, features: list[dict], source_text: dict[str, str], story_seq_offset: int) -> dict:
        """Return {'epic_id': str, 'stories': [AgentBStorySkeleton]} for S4.2."""

    @abstractmethod
    def plan_tasks(self, run_id: str, *, story: dict, feature: dict, source_text: dict[str, str], task_seq_offset: int, past_corrections: list[dict] | None = None, existing_tasks: list[dict] | None = None) -> dict:
        """Return {'story_id': str, 'tasks': [AgentBTaskOutput]} for S4.3."""
```

`MockAgentClient` implements all three by reading the existing `snake_escape_fixture.json` and slicing it to the requested epic/story scope. `plan_qa_tasks()` keeps returning the full bundle for `/demo-runs`.

`OpenAIAgentClient` implements all three with the B1/B2/B3 system prompts and JSON schemas from `Task-2-Agent-prompts-JSON.md`. It does NOT implement `plan_qa_tasks()`: for real provider the bundled method raises `NotImplementedError` (or delegates to a wrapper that runs B1→B2→B3 sequentially for non-streaming consumers; decide during implementation).

**Pipeline split** (in `app/services/pipeline.py`):

- `_stage_s4_1_epics(run)` — calls `plan_epics`, persists Epic[] (no stories/tasks yet), runs `validate_agent_b1_epic_coverage`, advances to `S4_1_AGENT_B_EPICS`, triggers `_sync_a1_epics(epics)`. Returns immediately so UI gets epic list quickly.
- `_stage_s4_2_stories(run)` — for each epic in repository, schedules an `AgentBJob{scope=epic}`. Uses `asyncio.gather` with `Semaphore(AGENT_B2_PARALLELISM)` (default 3). Each job calls `plan_stories`, persists Story[] for that epic, runs `validate_agent_b2_story_coverage(epic)`, triggers `_sync_a2_stories(epic, stories)`. Stage advances to `S4_2_AGENT_B_STORIES` after all jobs reach terminal state (success or failed-after-retry).
- `_stage_s4_3_tasks(run)` — for each story, schedules an `AgentBJob{scope=story}`. Same fan-out pattern with `Semaphore(AGENT_B3_PARALLELISM)` (default 5). Each job calls `plan_tasks`, persists QATask[] for that story. After all jobs terminal, runs `validate_agent_b3_full_plan` (schema + traceability + cross-story dedup + assignee + cross-epic dedup) and advances to `S4_3_AGENT_B_TASKS`, then to `S5_VALIDATION_B_SYNC`.

Each job's retry policy: schema fail → re-prompt with feedback × 2; transient HTTP error → exponential backoff × 2; timeout → mark `TIMEOUT`, NO auto-retry (manual retry via API).

**New endpoints** (in `app/api/v1/routes.py`):

- `POST /api/v1/runs/{run_id}/agent-b/epics` — preconditions: `current_stage == S3_VALIDATION_A`, HIL-1 cleared. Effect: run S4.1, return `{epics: [...]}`. Idempotent for the same `current_stage`.
- `POST /api/v1/runs/{run_id}/agent-b/stories` — preconditions: `current_stage == S4_1_AGENT_B_EPICS`. Effect: run S4.2 fan-out.
- `POST /api/v1/runs/{run_id}/agent-b/tasks` — preconditions: `current_stage == S4_2_AGENT_B_STORIES`. Effect: run S4.3 fan-out.
- `POST /api/v1/runs/{run_id}/agent-b/jobs/{job_id}/retry` — retry a single failed/timeout job (manual recovery from `<AgentBJobBoard>`).
- `GET /api/v1/runs/{run_id}/agent-b-jobs` — list `AgentBJob[]`. FE polls this every 2s during S4.2/S4.3.
- `PATCH /api/v1/runs/{run_id}/epics/{epic_id}` — Lead edit before S4.2. Body: `{title?, description?, feature_ids?}`. Reject if `current_stage != S4_1_AGENT_B_EPICS`.
- `POST /api/v1/runs/{run_id}/epics/merge` — body `{source_epic_ids: [...], target_title, target_description}`. Creates new epic, redirects features, deletes sources.
- `POST /api/v1/runs/{run_id}/epics/split` — body `{epic_id, splits: [{title, description, feature_ids}, ...]}`. Replaces source epic with N new epics.
- Existing `POST /api/v1/runs/{run_id}/agent-b` becomes a sequential wrapper (calls `_stage_s4_1_epics` → `_stage_s4_2_stories` → `_stage_s4_3_tasks` in turn) so `/demo-runs` and CLI smoke tests still work without code path change.

**New validators** (in `app/services/validators.py`):

- `validate_agent_b1_epic_coverage(run_id, epics, hil1_context) -> list[ValidationIssue]` — every approved feature must appear in exactly one epic (cross-cutting allowed in 2-3). Stable codes: `missing_b1_feature_coverage`, `extra_b1_feature_coverage`, `unknown_b1_feature_reference`.
- `validate_agent_b2_story_coverage(run_id, epic, stories, features) -> list[ValidationIssue]` — every feature in the epic has ≥1 story; story count guardrail. Stable codes: `missing_b2_story_for_feature`, `b2_story_count_out_of_range`.
- `validate_agent_b3_full_plan(run_id, epics, stories, tasks, features, sections) -> list[ValidationIssue]` — runs existing task validators PLUS mandatory cross-story / cross-epic dedup pass. Stable codes: existing + `duplicate_task_cross_story`, `duplicate_task_cross_epic`.

**Sync split** (in `app/services/pipeline.py`):

- `_sync_a1_epics(epics)` — runs after S4.1+V-B1. Sync events with `payload.sync_phase = "Sync-A1"`. Stores `epic_external_id → epic_page_id` mapping in `notion_sync` mock or real adapter.
- `_sync_a2_stories(epic, stories)` — runs per epic as soon as S4.2 succeeds for that epic. Sync events with `payload.sync_phase = "Sync-A2"`. Stores `story_external_id → story_page_id`.
- `_sync_b_tasks` — unchanged signature; now runs after S4.3+V-B3+HIL-2 (was after the bundled S4 + V-B). Sync events keep `payload.sync_phase = "Sync-B"`.

**Latency mitigations bundled into Phase 1.8 implementation (not their own phase per user decision):**

- Trim Agent B input: drop `dependencies` when empty, drop `delta_status` when null, cap `summary` at 200 chars. Done at `build_agent_b{1,2,3}_input()` payload assembly.
- Settings `AI_MODEL_AGENT_B1`, `AI_MODEL_AGENT_B2`, `AI_MODEL_AGENT_B3` with `gpt-4o-mini` default for B2/B3 (cheaper, faster) and `gpt-4o` default for B1 (fewer calls, more grounding).
- httpx timeout split: `OPENAI_TIMEOUT_CONNECT=10s`, `OPENAI_TIMEOUT_READ=120s` (per sub-call), `OPENAI_TIMEOUT_WRITE=10s`.
- Streaming response handling: switch `OpenAIAgentClient._post_response` to consume `text.delta` events. Inter-token gap, not total wall-time, drives `ReadTimeout`.
- Log `AgentRun.output_snapshot.timing` with `{wall_time_ms, output_tokens, input_tokens}` per sub-call for future tuning.

**Idempotency**: Task `external_id` seq is per `(project_id, feature_id)`, NOT per story or per run. Allocator runs in repository under transaction (Supabase) or under a per-feature lock (in-memory). This makes S4.3 retry-safe — failing one story's tasks does not interfere with sibling stories' tasks already persisted.

Acceptance:

- `/demo-runs` returns the same 8/5/5/11/44 counts as before (via legacy bundled path on `MockAgentClient.plan_qa_tasks`).
- Real-provider `/agent-b/epics` returns within 30s for a 25-feature input.
- Real-provider `/agent-b/stories` fan-out completes for 5-6 epics within 90s wall-time (parallel ≤3).
- Real-provider `/agent-b/tasks` fan-out completes for 20+ stories within 120s wall-time (parallel ≤5).
- A single failed B2 or B3 job leaves the rest of the plan intact; UI's job board can retry it.
- Cross-story/cross-epic dedup catches at least the `run_fc5f488fe767` failure shape if revisited.

### S5 Validation B + Router B + HIL-2

Target behavior:

- Validate schema, traceability, cross-agent feature references, approved-feature coverage, HIL-1 epic coverage, dedup, assignee sanity, confidence, and task count guardrails.
- Coverage validation compares output against `Run.session_memory["hil_1"].approved_feature_ids` and `Run.session_memory["hil_1"].epic_structure`.
- Missing coverage emits stable issue codes such as `missing_agent_b_feature_coverage` and `missing_agent_b_epic_coverage`.
- Router B lanes:
  - Auto: confidence `>=0.85`, no cross-cutting flag, no dedup flag
  - Batch: confidence `[0.65, 0.85)`
  - Block: confidence `<0.65` or dedup/cross-cutting flag
- HIL-2 provides batch review screens grouped by assignee and feature/epic.

Acceptance:

- Agent B cannot advance with the `run_1cefe76fe58c` failure shape: one gameplay-only epic while approved non-gameplay features remain uncovered.
- Only approved or auto-approved tasks are eligible for task sync and Agent C.
- Sync-A/B is not called when Agent B coverage retries are exhausted.

### S5b Notion Sync

Task 3 refines sync into three sub-events. Backend may keep S5b/S7b stage labels, but implementation must distinguish:

- Sync-A: Epic + Story after HIL-1.
- Sync-B: Task after HIL-2 or Router B auto-approval.
- Sync-C: Test Case after HIL-3 or Router C auto-approval.

Target behavior:

- Notion is destination only; pipeline state is source of truth.
- Upsert by `external_id`, never title/description.
- Sync failure does not block downstream pipeline work.
- Retry with backoff; use dead-letter queue after max retries.
- Maintain external_id -> Notion page_id mapping for relations.

Acceptance:

- Sync events preserve payload, action, status, retry count, and error.
- Replay can resume from pipeline state without duplicates.

### S6 Agent C - Test Case Generator

Target behavior from Task 2:

- Trigger per approved task, without waiting for all tasks to be approved.
- Input: one approved task, feature context, and source section text.
- Output test cases covering positive, negative, edge, and integration categories.
- One assertion per expected result.
- Concrete preconditions/test_data; RNG-dependent tests require seed or non-deterministic marker.

Acceptance:

- Each eligible task has required category coverage or explicit `[GAP]` placeholder.
- Test cases inherit task priority and source sections.

### S7 Validation C + HIL-3

Target behavior:

- Validate schema, source traceability, four-category coverage, repeatability, forbidden vague phrases, one-assertion expected result, and related task links.
- Assignees review their own test cases in HIL-3.
- Lead review is not required for every test case unless risk rules trigger it.

Acceptance:

- Invalid or incomplete-source test cases cannot auto-sync.

### S7b Test Case Sync

Target behavior:

- Sync-C appends or upserts test cases in Notion.
- Link test cases to task pages by Notion page_id resolved from `external_id`.
- Update task status from `Ready for Test Cases` to `Test Cases Ready` when appropriate.

Acceptance:

- Test case sync is idempotent and replayable.

### Final Coverage Report + Sign-off

Target behavior:

- Report section coverage, story coverage, assignee distribution, P0/P1/P2 ratio, validation issues, sync status, risk metrics, and sign-off.
- Notify QA Lead via email/Slack with report and Notion links.
- Lead sign-off completes the workflow.

Acceptance:

- One run can show traceability from GDD version to section, feature, task, test case, validation issue, sync event, risk event, and sign-off.

## Cross-Cutting Backend Requirements

- All successful public API responses keep `{ data, meta, error }`.
- Mock providers remain the default for local demo and tests.
- Supabase persistence remains optional until explicitly configured.
- Real agents must use structured JSON output and schema validation.
- Validation and risk handling must use stable issue/event codes.
- Session memory is per-run; long-term memory is per-project.
- Every auto-decision logs a reason.
- Stage boundaries from Task 1 are authoritative.

## Backend Acceptance Criteria

- `pytest` passes in `backend/`.
- `python -m ruff check .` passes in `backend/`.
- Swagger can still run `/api/v1/demo-runs`.
- Target Stage 0 can create a run from upload + project selection without parsing the file.
- Target S1 can register/version/parse the uploaded GDD and produce HIL-0/DELTA context.
- Per-stage endpoints can advance a run from S1 through Agent A, HIL-1, Agent B, HIL-2, Agent C, HIL-3, and Finalize without using `/demo-runs`.
- Agent B coverage validation blocks partial real-provider plans before Sync-A/B and records actionable validation/risk evidence for retry or HIL follow-up.
- Bulk HIL-0 resolution works for the dashboard's "Proceed with flag" action and does not fan out parallel writes.
