# Frontend Slice Tasks

This checklist tracks the Next.js demo app against `frontend/PLAN.md` and the four root source-of-truth solution files. Each task includes a verification step so implementation can proceed screen by screen without relying on hidden assumptions.

Progress rule: when a task in this file is completed, update its checkbox from `[ ]` to `[x]` in the same implementation turn or commit, and keep the `Verify:` line directly below it.

## Status Snapshot (last reviewed 2026-05-11)

| Phase | Done / Total | Status |
|---|---|---|
| F0 - Scaffold + Providers | 5 / 8 | Next.js + shadcn + Providers (QueryClient + Theme + Toaster + Devtools) shipped; `lib/api.ts`, `lib/queries.ts`, `lib/mutations.ts`, `_design_fixtures/`, `.env.local.example` pending. |
| F1 - AppShell + Provider Status + Navigation | 0 / 3 | Foundation for every other screen. |
| F2 - Projects + GDD Version History | 0 / 4 | List, create, detail, version-history rows. |
| F3 - Run Dashboard | 0 / 4 | Timeline, coverage, agent runs, inspection tabs. |
| F4 - HIL Queues (HIL-0 / 1 / 2 / 3) | 0 / 3 | One route template; tier param drives queue + mutation shape. |
| F5 - Inspection Tables | 0 / 2 | Reusable `<ArtifactTable>` + detail drawer. |
| F6 - Sync Log + Risk Center | 0 / 3 | Sync log, risk grouped table, kill-switch banner. |
| F7 - Sign-Off + Final Report | 0 / 2 | Sign-off button, printable report. |
| F8 - Verification + Submission Polish | 0 / 5 | Lint, build, end-to-end walkthrough, screenshots, README. |

## Next Implementation Slice — `lib/api.ts` + `lib/queries.ts` + `lib/mutations.ts` + `_design_fixtures/`

Before opening Claude Design for any screen, the data layer needs to be in place so each generated artifact has hooks to wire against during the Claude Code handoff. Recommended order in one implementation slice:

1. Add `frontend/.env.local.example` and document `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000/api/v1`. Copy to `.env.local`.
2. Write `frontend/src/lib/types.ts` mirroring backend Pydantic models: `Run`, `Project`, `GDDDocument`, `Feature` (with `lane` + `delta_status`), `Epic`, `Story`, `QATask`, `TestCase`, `ValidationIssue`, `RiskEvent`, `SyncEvent`, `AgentRun`, `ReviewDecision`, `ReviewQueueItem` / `ReviewQueueGroup` / `ReviewQueue`, `StageEvent`, `HIL0Question`, `HIL0Resolution`.
3. Write `frontend/src/lib/api.ts` envelope-aware fetch wrapper that throws on `error` and returns `data` typed as `T`.
4. Write `frontend/src/lib/queries.ts` with one `useXxx` hook per endpoint (about 20 hooks). Centralise query keys in a `queryKeys` constant for invalidation symmetry.
5. Write `frontend/src/lib/mutations.ts` with hooks for `useTriggerRun`, `useLoadContext`, `useCreateProject`, `useCreateReviewDecision`, `useResolveHil0Question`, `useSignOffRun`, `useReplaySync`. Each mutation invalidates the relevant query keys.
6. Dump representative JSON for every endpoint into `frontend/_design_fixtures/` (trim each file to 2–3 records + 1 edge case). Add `frontend/_design_fixtures/design-system.md` cheat sheet for Claude Design.
7. Verify: `npm run lint` + `npx tsc --noEmit` clean from `frontend/`.

After this slice is green, F1 (AppShell) opens in Claude Design with the linked codebase + fixture context.

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

- [ ] Task: Add `frontend/.env.local.example` documenting `NEXT_PUBLIC_API_BASE` and instructing the reader to copy to `.env.local`.
  Verify: `frontend/.env.local.example` exists; `frontend/.gitignore` ignores `.env.local` but not the example.

- [ ] Task: Write `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/mutations.ts` covering every `/api/v1` endpoint listed in `backend/app/api/v1/routes.py`.
  Verify: `npx tsc --noEmit` from `frontend/` passes; every route in `routes.py` has a corresponding `useXxx` hook.

- [ ] Task: Dump representative JSON for every endpoint into `frontend/_design_fixtures/` (trimmed to 2–3 records + 1 edge case per file) and add `frontend/_design_fixtures/design-system.md`.
  Verify: `ls frontend/_design_fixtures/*.json | wc -l` returns ≥ 16 (matches `backend/app/api/v1/routes.py` GET endpoints + key POST samples).

## Phase F1 — AppShell + Provider Status + Navigation

- [ ] Task: Generate `<AppShell>` in Claude Design (linked subdirectory: `frontend/`), handoff to Claude Code, port into `frontend/src/components/app-shell.tsx`. Header (56px) with breadcrumbs from `usePathname()`, provider pills, "Sign off run" button. Left sidebar (256px) with Projects, Runs, HIL Queues (collapsible HIL-0..HIL-3), Sync Log, Risk Center, Settings.
  Verify: Every route renders through `<AppShell>`; `npm run lint` clean.

- [ ] Task: Implement `<ProviderStatusPills>` reading `GET /api/v1/providers/status` via `useProvidersStatus()`; pill colour reflects `credentials_ready`. Click opens a dialog with provider details and a link to `frontend/README.md` env section.
  Verify: With `AI_PROVIDER=mock NOTION_PROVIDER=mock REPOSITORY_PROVIDER=memory`, all three pills show green; with `NOTION_PROVIDER=real NOTION_TOKEN=""`, Notion pill shows red.

- [ ] Task: Sidebar navigation uses Next.js `<Link>`; active item highlighted by indigo-500 left border + slate-800 background; collapsible on viewports `< lg`.
  Verify: Navigating between `/projects` and `/runs/<id>` is client-side (no full reload visible in DevTools Network).

## Phase F2 — Projects + GDD Version History

- [ ] Task: Build `/projects` list page reading `GET /api/v1/projects`. Empty state when no projects exist with a "Create your first project" CTA.
  Verify: After scaffolded backend run, page lists `Snake Escape` plus any test projects.

- [ ] Task: Build `<NewProjectDialog>` calling `useCreateProject()` then `useTriggerRun()` with `project_name` for `NEW_GAME` mode. Form uses `react-hook-form` + `zod`; submit toasts success and navigates to `/runs/<run_id>`.
  Verify: Creating a project + triggering returns a run with `mode=NEW_GAME`; toast appears; URL changes to `/runs/run_xxx`.

- [ ] Task: Build `/projects/[project_id]` detail page showing project metadata, runs scoped to the project, and a "Trigger DELTA run" button calling `useTriggerRun()` with `project_id` for `DELTA` mode.
  Verify: DELTA trigger returns `mode=DELTA`; navigation to the new run shows `parent_document_id` on the registered GDD.

- [ ] Task: Add GDD version history strip on `/projects/[project_id]` consuming `GET /api/v1/projects/{project_id}/gdd-documents`; show `version_id`, `description_status` badge (`PENDING` / `USER_PROVIDED` / `AI_GENERATED`), `parent_document_id` chain, and file metadata.
  Verify: Two GDDs registered under one project show `v2 → v1` chain ordered latest-first.

## Phase F3 — Run Dashboard

- [ ] Task: Build `/runs/[run_id]` page with vertical timeline from `GET /api/v1/runs/{run_id}/timeline`; each `StageEvent` rendered as a card with stage name, status, timestamp, message.
  Verify: Snake Escape demo timeline shows 9 stages from `S0_TRIGGER` to `FINAL_COVERAGE`.

- [ ] Task: Build coverage cards from `GET /api/v1/runs/{run_id}/coverage`: section counts, feature/task/test-case counts, `risk_summary`, `sync_summary`, `gdd_version_metadata`, `sign_off`.
  Verify: Demo coverage shows `task_count: 11`, `test_case_count: 44`, `risk_summary.total > 0`, `sync_summary.by_phase` containing `Sync-A`, `Sync-B`, `Sync-C`.

- [ ] Task: Build agent runs panel from `GET /api/v1/runs/{run_id}/agent-runs`. Agent A row exposes `output_snapshot.attempt_count` + `retry_exhausted`; expand button shows the `attempts[]` log.
  Verify: With a demo run, Agent A row shows `attempt_count=1, retry_exhausted=false`; with a fixture forcing retries, the row shows >1 attempts in the log.

- [ ] Task: Add inspection tabs (Features / Epics / Stories / Tasks / Test Cases / Validation Issues) consuming the reusable `<ArtifactTable>` (Phase F5).
  Verify: Switching tabs does not re-fetch — react-query cache covers all six artifact types after dashboard load.

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

- [ ] Task: Manual end-to-end walkthrough — create project → trigger NEW_GAME → walk HIL-0..HIL-3 → approve at least one task → see Sync-A/B/C in sync log → see risk events → sign off → second run on same project triggers DELTA + version history shows `v1, v2`.
  Verify: All eight steps complete without console errors.

- [ ] Task: `npm run lint` clean from `frontend/`.
  Verify: Exit code 0.

- [ ] Task: `npm run build` clean from `frontend/`.
  Verify: Exit code 0; `.next/` build output present.

- [ ] Task: Capture six submission screenshots — AppShell with provider pills, Run dashboard with timeline + coverage, HIL-2 queue, Sync log filtered by Sync-B, Risk center, signed-off coverage report. Store under `docs/screenshots/`.
  Verify: All six PNGs exist under `docs/screenshots/` and are linked from `frontend/README.md`.

- [ ] Task: Write `frontend/README.md` documenting `npm install`, `npm run dev`, env variables, and the screenshot capture workflow.
  Verify: A new user can follow the README and reproduce the happy-path demo end-to-end.
