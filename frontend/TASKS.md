# Frontend Slice Tasks

This checklist tracks the Next.js demo app against `frontend/PLAN.md` and the four root source-of-truth solution files. Each task includes a verification step so implementation can proceed screen by screen without relying on hidden assumptions.

Progress rule: when a task in this file is completed, update its checkbox from `[ ]` to `[x]` in the same implementation turn or commit, and keep the `Verify:` line directly below it.

## Status Snapshot (last reviewed 2026-05-12 - Phase 1.8 UI implementation landed)

| Phase | Done / Total | Status |
|---|---|---|
| F0 - Scaffold + Providers | 9 / 9 | Scaffold, providers, env example, typed API/query/mutation layer, design fixtures, and offline Google font build support shipped. |
| F1 - AppShell + Provider Status + Navigation | 4 / 4 | Shared AppShell, live provider pills, desktop sidebar navigation, provider details dialog, and mobile drawer shipped. |
| F2 - Projects + GDD Version History | 4 / 4 | Project list, new project dialog, project detail, DELTA trigger, and GDD version-history rows shipped. |
| F3 - Run Dashboard | 6 / 6 | Timeline, Load Context CTA, coverage, agent runs, artifact tabs, design alignment, and hydration fix shipped. |
| F3.5 - Stage-Aware CTA + Inline HIL Approve | 6 / 6 | `<NextStagePanel>`, stage mutation hooks, bulk HIL-0, inline HIL approvals, sequential bulk approvals, and 409 recovery shipped. |
| **F3.6 - Agent B Hierarchical UI (Phase 1.8)** | **7 / 10** | Types/hooks, `<NextStagePanel>` substage state machine, `<AgentBJobBoard>`, and `<EpicReviewPanel>` title edit + merge/split shipped. Remaining: drag/dialog polish, nested streaming epics tab, dedicated walkthrough artifact. |
| F4 - HIL Queues (HIL-0 / 1 / 2 / 3) | 0 / 3 | Dedicated deep-link routes; re-uses the inline approve list from F3.5. |
| F5 - Inspection Tables | 0 / 2 | Reusable `<ArtifactTable>` + detail drawer. |
| F6 - Sync Log + Risk Center | 0 / 3 | Sync log, risk grouped table, kill-switch banner. |
| F7 - Sign-Off + Final Report | 0 / 2 | Sign-off button, printable report. |
| F8 - Verification + Submission Polish | 3 / 6 | Lint/typecheck/build pass; HTTP smoke completed separately; browser walkthrough, screenshots, and README remain. |

## Next Implementation Slice - Deep Links, Screenshots, And README

The run dashboard can now drive the stepped mock-mode pipeline end to end: `Load Context` creates HIL-0 questions, `Proceed with flag (n)` resolves the HIL-0 batch in one backend request, Agent A/B/C advance through blocking HIL-1/2/3 gates, and Finalize completes the run. The frontend also keeps `next/font/google` restored while `npm run build` works offline through checked-in mocked font responses.

Implementation order:

1. **F8 manual walkthrough** - create a NEW_GAME run and capture the full `Load Context -> HIL-0 -> Agent A -> HIL-1 -> Agent B -> HIL-2 -> Agent C -> HIL-3 -> Finalize -> Sign off` path.
2. **F4 dedicated HIL routes** - build `/runs/[run_id]/hil/[tier]` as deep links that reuse the inline queue rendering and mutation behavior.
3. **F6/F7 submission pages** - finish sync log, risk center, sign-off report, and print styles.
4. **Frontend README + screenshots** - document env setup, offline font behavior, demo walkthrough, and screenshot capture.

F5 reusable table/detail cleanup remains useful polish, but it is no longer on the critical path for proving the staged workflow.

## Phase F0 — Scaffold + Providers

- [x] Task: Scaffold Next.js 16 App Router project under `frontend/` with TypeScript, Tailwind, ESLint, `src/` directory, and `@/*` alias.
  Verify: `frontend/package.json` includes Next 16 + React 19; `npm run dev` opens `http://localhost:3000`.

- [x] Task: Install runtime dependencies — `@tanstack/react-query` + devtools, `next-themes`, `sonner`, `lucide-react`, `react-hook-form` + `@hookform/resolvers`, `zod`, `clsx`, `tailwind-merge`, `class-variance-authority`.
  Verify: `frontend/package.json` lists all of the above.

- [x] Task: Add shadcn primitives — button, card, badge, table, tabs, dialog, input, input-group, select, textarea, separator, skeleton, sonner, dropdown-menu, sheet, command.
  Verify: `frontend/src/components/ui/` contains one file per primitive.

- [x] Task: Implement `frontend/src/app/providers.tsx` wrapping `QueryClientProvider` (singleton browser client via `isServer` check + `useState` lazy init), `ThemeProvider` (default `dark`, `attribute="class"`, `disableTransitionOnChange`), Sonner `<Toaster>` (bottom-right, richColors, closeButton), and `<ReactQueryDevtools>` (dev-only, bottom-left).
  Verify: `frontend/src/app/providers.tsx` exists and typechecks; provider defaults match `frontend/PLAN.md` rationale.

- [x] Task: Wire `frontend/src/app/layout.tsx` to mount `<Providers>` around `{children}`, set product metadata, and `suppressHydrationWarning` on `<html>` for `next-themes`.
  Verify: `npx tsc --noEmit` passes; `npm run dev` renders the default Next.js page through `<Providers>`.

- [x] Task: Add `frontend/.env.local.example` documenting `NEXT_PUBLIC_API_BASE` and instructing the reader to copy to `.env.local`.
  Verify: `frontend/.env.local.example` exists; `frontend/.gitignore` ignores `.env.local` but not the example.

- [x] Task: Write `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/mutations.ts` covering every `/api/v1` endpoint listed in `backend/app/api/v1/routes.py`.
  Verify: `npx tsc --noEmit` from `frontend/` passes; every route in `routes.py` has a corresponding `useXxx` hook.

- [x] Task: Dump representative JSON for every endpoint into `frontend/_design_fixtures/` (trimmed to 2–3 records + 1 edge case per file) and add `frontend/_design_fixtures/design-system.md`.
  Verify: `Get-ChildItem frontend/_design_fixtures -Filter *.json` returns 17 JSON files and `frontend/_design_fixtures/design-system.md` exists.

- [x] Task: Restore `next/font/google` while keeping offline dev/build support.
  Verify: `layout.tsx` imports `Inter` and `JetBrains_Mono` from `next/font/google`; `next.config.ts` sets `NEXT_FONT_GOOGLE_MOCKED_RESPONSES`; checked-in WOFF2 files live under `src/app/fonts/google/`; `npm run build` passes offline.

## Phase F1 — AppShell + Provider Status + Navigation

- [x] Task: Port `<AppShell>` into `frontend/src/components/app-shell.tsx` and mount it from `frontend/src/app/layout.tsx`. Header is 56px with provider pills + search; sidebar is 256px with workspace/current-run/settings navigation.
  Verify: Browser check on `/runs/run_87a8f69786fc` shows `header` height `56px`, `aside` width `256px`, and `npm run lint` clean.

- [x] Task: Implement `<ProviderStatusPills>` reading `GET /api/v1/providers/status` via `useProvidersStatus()`; pill colour reflects `credentials_ready`.
  Verify: Browser check on the running backend shows live pills such as `AI openai`, `Notion real`, and `repo supabase`; unavailable credentials render the red pill style.

- [x] Task: Sidebar navigation uses Next.js `<Link>` and active state from `usePathname()` for Projects, Runs, Dashboard, HIL queue, Sync log, Risk, Sign off, and Settings.
  Verify: Current run links are generated from `/runs/<id>` and active items render with indigo/slate styling.

- [x] Task: Add remaining AppShell polish: provider details dialog and mobile sidebar drawer for viewports `< lg`.
  Verify: Browser check on `/projects` confirms provider pill opens the details dialog; mobile viewport hides the desktop aside and opens navigation from the menu button.

## Phase F2 — Projects + GDD Version History

- [x] Task: Build `/projects` list page reading `GET /api/v1/projects`. Empty state when no projects exist with a "Create your first project" CTA.
  Verify: Browser check on `/projects` lists `Snake Escape`, shows project/run summary metrics, and keeps the empty-state CTA in place for zero-project backends.

- [x] Task: Build `<NewProjectDialog>` with `react-hook-form` + `zod`; it exposes a create-record action through `useCreateProject()` and a primary create+trigger action through `useTriggerRun()` with `project_name` for backend-owned `NEW_GAME` creation.
  Verify: Browser check opens the dialog and validates the default GDD file field; TypeScript covers the `useTriggerRun()` payload and `/runs/<run_id>` navigation path. The trigger action intentionally lands on an S0 run; S1 is started from the run dashboard.

- [x] Task: Build `/projects/[project_id]` detail page showing project metadata, runs scoped to the project, and a "Trigger DELTA run" button calling `useTriggerRun()` with `project_id` for `DELTA` mode.
  Verify: Browser check on `/projects/snake-escape` shows metadata, run history, and the DELTA dialog with the project source document prefilled.

- [x] Task: Add GDD version history strip on `/projects/[project_id]` consuming `GET /api/v1/projects/{project_id}/gdd-documents`; show `version_id`, `description_status` badge (`PENDING` / `USER_PROVIDED` / `AI_GENERATED`), `parent_document_id` chain, and file metadata.
  Verify: Browser check on `/projects/snake-escape` shows the GDD version history section; rows are sorted latest-first and include version, status, parent, size, origin, and SHA metadata.

## Phase F3 — Run Dashboard

- [x] Task: Build `/runs/[run_id]` page with vertical timeline from `GET /api/v1/runs/{run_id}/timeline`; each `StageEvent` rendered as a card with stage name, status, timestamp, message.
  Verify: Snake Escape demo timeline shows 9 stages from `S0_TRIGGER` to `FINAL_COVERAGE`.

- [x] Task: Add staged `Load Context` UX for runs still at `S0_TRIGGER`; button calls `useLoadContext()` and refreshes run, runs list, timeline, coverage, sections, GDD documents, and HIL-0 questions.
  Verify: A newly triggered project run shows the `Load Context` CTA; clicking it advances the dashboard to `S1_CONTEXT_LOADER` and populates GDD metadata/section counts without a page reload.

- [x] Task: Build coverage cards from `GET /api/v1/runs/{run_id}/coverage`: section counts, feature/task/test-case counts, `risk_summary`, `sync_summary`, `gdd_version_metadata`, `sign_off`.
  Verify: `/runs/run_87a8f69786fc` renders coverage percentage, total/actionable sections, generated artifact counts, risk by severity/code, sync by phase, GDD metadata, and sign-off state.

- [x] Task: Build agent runs panel from `GET /api/v1/runs/{run_id}/agent-runs`. Agent A row exposes `output_snapshot.attempt_count` + `retry_exhausted`; expand button shows the `attempts[]` log.
  Verify: `/runs/run_87a8f69786fc` shows Agent A attempt count/retry state and expandable attempt log.

- [x] Task: Add inspection tabs (Features / Epics / Stories / Tasks / Test Cases / Validation Issues) with route-local table components.
  Verify: All six tabs consume their typed query hooks and render backend payloads; reusable `<ArtifactTable>` extraction remains tracked in Phase F5.

- [x] Task: Align dashboard visual shell with `ui-design/qa-runs-dashboard` and fix invalid HTML hydration warning.
  Verify: Browser check shows Inter font, slate/indigo tokens, AppShell/sidebar/header, and no `<div>`-inside-`<p>` hydration warning.

## Phase F3.5 — Stage-Aware Dashboard CTA + Inline HIL Approve

Depends on root Phase 1.5 backend endpoints (`/agent-a`, `/agent-b`, `/agent-c`, `/finalize`).

- [x] Task: Add `useRunAgentA`, `useRunAgentB`, `useRunAgentC`, `useFinalizeRun` mutation hooks in `src/lib/mutations.ts`. Each invalidates run / timeline / coverage / agent-runs / sync-events / risk-events / validation-issues plus the four review queues. On `ApiError.code === "hil_gate_blocked"`, toast description should name the offending tier + count.
  Verify: `npx tsc --noEmit` clean from `frontend/`; each hook is exported and used from the dashboard.

- [x] Task: Replace the hard-coded `Load Context` CTA with `<NextStagePanel>` in `src/app/runs/[id]/page.tsx`. The panel reads `useRun`, `useHil0Questions`, and (lazily) the relevant `useReviewQueue("HIL-1"|"HIL-2"|"HIL-3")` based on `current_stage`. It renders one primary action mapping `current_stage` → mutation per the table in `frontend/PLAN.md` Screen 3.5.
  Verify: For a freshly triggered NEW_GAME run, the panel walks through `Load Context → Run Agent A → Approve HIL-1 → Run Agent B → Approve HIL-2 → Run Agent C → Approve HIL-3 → Finalize → Sign off` without a page reload or terminal.

- [x] Task: Add inline HIL approve list under `<NextStagePanel>` for HIL-1/2/3. Each item shows `target_id`, `title`, `lane`, `review_status` plus Approve / Reject buttons calling `useCreateReviewDecision`. A bulk `Approve all in queue` button fans out into N mutations with one aggregated toast.
  Verify: Leaving one feature in `NEEDS_REVIEW` causes the `Run Agent B` button to disable with a "blocked by HIL-1" badge; clicking `Approve all in queue` re-enables it.

- [x] Task: Handle 409 error paths from stage mutations. `hil_gate_blocked` scrolls the inline HIL list into view; `wrong_stage` refetches `useRun`; `kill_switch_tripped` locks the panel and surfaces the red banner the dashboard already renders for `run.session_memory.kill_switch.tripped`.
  Verify: Manual test by replaying a stale stage mutation — UI recovers gracefully without a hard refresh.

- [x] Task: Add bulk HIL-0 resolution hook and wire `Proceed with flag (n)` to one backend request.
  Verify: `useResolveHil0Questions()` posts to `/runs/{runId}/hil-0/resolutions/bulk`; dashboard no longer calls `Promise.all` for HIL-0.

- [x] Task: Make bulk HIL-1/2/3 approvals sequential.
  Verify: `approveItems()` awaits each `useCreateReviewDecision` mutation in order, avoiding request bursts against Supabase/PostgREST.

## Phase F3.6 — Agent B Hierarchical UI (Phase 1.8)

Depends on backend Phase 1.8 endpoints (`/agent-b/epics`, `/agent-b/stories`, `/agent-b/tasks`, `/agent-b-jobs`, `/agent-b/jobs/{id}/retry`, `PATCH /epics/{id}`, `/epics/merge`, `/epics/split`). Implementation tasks below; landing them requires the backend phase first.

- [x] Task: Extend `src/lib/types.ts` with `AgentBJob`, `AgentBScope`, `AgentBJobStatus`, `EpicMergeRequest`, `EpicSplitRequest`, `EpicPatchRequest`. Mirror backend Pydantic models.
  Verify: `npx tsc --noEmit` clean.

- [x] Task: Add typed query hooks `useAgentBJobs(runId, { enabled })` (polling 2s when enabled), `useEpicEditAuditLog(runId)` (optional, for debugging) in `src/lib/queries.ts`.
  Verify: Hook returns `AgentBJob[]` from `/api/v1/runs/{run_id}/agent-b-jobs`; polling stops when all jobs terminal.

- [x] Task: Add typed mutation hooks `useRunAgentBEpics(runId)`, `useRunAgentBStories(runId)`, `useRunAgentBTasks(runId)`, `useRetryAgentBJob(runId, jobId)`, `useUpdateEpic(runId, epicId)`, `useMergeEpics(runId)`, `useSplitEpic(runId)` in `src/lib/mutations.ts`. Each invalidates run + timeline + agent-runs + jobs + epics + stories + tasks query keys as appropriate.
  Verify: `npx tsc --noEmit` clean; each hook is exported and consumed by Screen 3.6.

- [x] Task: Update `<NextStagePanel>` state machine for the new stages. Insert `S4_1_AGENT_B_EPICS`, `S4_2_AGENT_B_STORIES`, `S4_3_AGENT_B_TASKS` branches. Replace single `Run Agent B` button with the three substage actions per the table in `frontend/PLAN.md` Screen 3.6.
  Verify: Manually walk a NEW_GAME run from S3 to S5 with mock fixture; the panel advances `Run Agent B (Epics)` → `<EpicReviewPanel>` + `Continue to Stories` → fan-out spinner → `<AgentBJobBoard>` → `Run Agent B (Tasks)` → fan-out → HIL-2.

- [x] Task: Build `<AgentBJobBoard>` component under `src/app/runs/[id]/_components/agent-b-job-board.tsx`. Four columns (Queued/Running/Done/Failed), per-job card with scope_type + scope_id + attempt_count + elapsed + error. Top toolbar `Retry all failed` (sequential mutations), `Refresh`.
  Verify: Storybook fixture or local test renders the board with a mix of statuses; clicking `Retry` calls `useRetryAgentBJob` exactly once per card.

- [x] Task: Build `<EpicReviewPanel>` component under `src/app/runs/[id]/_components/epic-review-panel.tsx`. Epic cards support inline title editing plus selected-epic Merge / Split actions before S4.2 locks the epic set. Drag/drop reassignment and delete/reassign remain polish.
  Verify: Editing epic title, dragging one feature, and clicking `Continue` produces (a) a `PATCH /epics/{id}` for the title, (b) a `PATCH` for each epic affected by the drag, (c) the subsequent `Run Agent B (Stories)` call uses the patched state.

- [ ] Task: Build `<MergeEpicsDialog>` and `<SplitEpicDialog>` (shadcn `<Dialog>`). Merge: checkbox list of other epics + title/description form. Split: dynamic form with N new-epic rows + drag-style feature assignment. Both validate exhaustive feature coverage before allowing submit.
  Verify: Submit disabled until validation passes; success invalidates `useEpics(runId)`.

- [ ] Task: Update the Epics tab on `/runs/[run_id]` to expand stories nested under each epic as Sync-A2 events arrive. During S4.2, an epic with no stories yet renders a small spinner; once `useStories(runId).data` includes stories for that epic_id, render the stories inline.
  Verify: With a fake backend that delivers stories for epic A first, then B, then C, the UI renders A's stories while B and C still show spinners.

- [x] Task: Wire 409 error handling for new stage mutations. `agent_b_substage_blocked` should scroll the job board into view; `wrong_stage` refetches run; partial-failure response triggers `<AgentBJobBoard>` "Retry failed" highlight.
  Verify: Manually trigger each error path (e.g. call `/agent-b/stories` while at `S4_2_AGENT_B_STORIES` already, with one failed job) and confirm UX recovers.

- [ ] Task: Add Cypress or Playwright walkthrough (or at least a manual checklist in `frontend/README.md`) covering the new Agent B substage flow: trigger run → S0 → S1 → HIL-0 bulk proceed → Agent A → HIL-1 inline approve → Agent B Epics → edit one epic title + drag one feature → Continue to Stories → wait fan-out → Continue to Tasks → wait fan-out → HIL-2 inline approve → Agent C → HIL-3 → Finalize → Sign off.
  Verify: All steps complete without console errors; final coverage shows expected counts.

## Phase F4 — HIL Queues

- [ ] Task: Build `/runs/[run_id]/hil/[tier]` route template reading `GET /api/v1/runs/{run_id}/review-queues/{HIL-tier}` and rendering grouped cards by reviewer / feature / epic.
  Verify: For Snake Escape demo, HIL-1 shows 2 items, HIL-2 shows 2 items, HIL-3 shows 8 items.

- [ ] Task: HIL-0 form posts `useResolveHil0Question()` with `action` in `{provide_artifact, proceed_with_flag, skip_section}`. Each question card shows section title + reason + question + 3 action buttons.
  Verify: Resolving a HIL-0 question removes it from the queue and toasts success.

- [ ] Task: HIL-1 / HIL-2 / HIL-3 cards expose Approve / Reject / Block actions calling `useCreateReviewDecision()`. Bulk approve at group level fans out into individual mutations with a single aggregated toast.
  Verify: Approving a BATCH-lane task at HIL-2 flips its `lane` to AUTO in `/runs/[run_id]` (mirrors `test_review_decision_approval_updates_lane_and_removes_item_from_queue`).

## Phase F5 — Inspection Tables

- [ ] Task: Build `<ArtifactTable>` reusable component accepting a column definition + dataset. Common columns: `target_id` (monospace chip), title, lane badge, review_status badge, source_sections chip list, confidence sparkbar. Feature extras: `delta_status` badge + cross-cutting flag. Task extras: assignee chip, priority, estimate, status. Test case extras: category badge, type, related task chip. Validation issue extras: severity (S1/S2/S3) badge, code, stage.
  Verify: All six artifact tabs render through `<ArtifactTable>` with type-safe column definitions.

- [ ] Task: Add `<ArtifactDetailDrawer>` (shadcn `<Sheet>`) opened on row click; shows the full payload pretty-printed and any related artifacts (e.g. a Task's linked Feature + Test Cases).
  Verify: Drawer contents match the same fields returned by `GET /api/v1/runs/{run_id}/{artifact_type}`.

## Phase F6 — Sync Log + Risk Center

- [ ] Task: Build `/runs/[run_id]/sync-log` page reading `GET /api/v1/runs/{run_id}/sync-events`; filter pills by `payload.sync_phase` (`Sync-A` / `Sync-B` / `Sync-C`); table columns include `external_id`, `notion_page_id`, `target_type`, `action`, `status`, `retry_count`; row action calls `useReplaySync()`.
  Verify: Snake Escape demo shows 10 Sync-A + 9 Sync-B + 36 Sync-C events when no filter is applied.

- [ ] Task: Build `/runs/[run_id]/risk` page reading `GET /api/v1/runs/{run_id}/risk-events`; grouped table by severity (S1 / S2 / S3) showing `code`, `summary`, `target_type`, `target_id`, `owner_action`.
  Verify: Snake Escape demo shows ≥1 `uncovered_actionable_section` event under S2.

- [ ] Task: Add a kill-switch banner at the top of `/runs/[run_id]/risk` when `coverage.risk_summary.by_severity.S1 >= 3` or `run.status === FAILED` with a `kill_switch_tripped` event. Banner explains the threshold and links to the offending events.
  Verify: With a fixture that fakes 3 S1 events, banner renders; without, banner is hidden.

## Phase F7 — Sign-Off + Final Report

- [ ] Task: Build `/runs/[run_id]/sign-off` page rendering a printable summary of the coverage payload plus a Sign Off button calling `useSignOffRun()` with the current reviewer. Button disabled when `run.status !== COMPLETED` or kill switch tripped.
  Verify: Signing off updates `signed_off_by` / `signed_off_at` on the run and the `coverage_report.sign_off` block (mirrors `test_sign_off_endpoint_updates_run_and_coverage_report`).

- [ ] Task: Add `@media print` stylesheet that hides the AppShell + sidebar + buttons and keeps only the printable report.
  Verify: `Ctrl+P` preview shows the report without chrome.

## Phase F8 — Verification + Submission Polish

- [ ] Task: Manual end-to-end walkthrough — create project → trigger NEW_GAME at S0 → open run dashboard → Load Context for S1 → walk HIL-0..HIL-3 → approve at least one task → see Sync-A/B/C in sync log → see risk events → sign off → second run on same project triggers DELTA + version history shows `v1, v2`.
  Verify: All eight steps complete without console errors.

- [x] Task: `npm run lint` clean from `frontend/`.
  Verify: Exit code 0.

- [x] Task: `npx tsc --noEmit` clean from `frontend/`.
  Verify: Exit code 0.

- [x] Task: `npm run build` clean from `frontend/`.
  Verify: Exit code 0; `.next/` build output present.

- [ ] Task: Capture six submission screenshots — AppShell with provider pills, Run dashboard with timeline + coverage, HIL-2 queue, Sync log filtered by Sync-B, Risk center, signed-off coverage report. Store under `docs/screenshots/`.
  Verify: All six PNGs exist under `docs/screenshots/` and are linked from `frontend/README.md`.

- [ ] Task: Write `frontend/README.md` documenting `npm install`, `npm run dev`, env variables, and the screenshot capture workflow.
  Verify: A new user can follow the README and reproduce the happy-path demo end-to-end.
