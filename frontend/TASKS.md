# Frontend Slice Tasks

This checklist tracks the Next.js demo app against `frontend/PLAN.md` and the four root source-of-truth solution files. Each task includes a verification step so implementation can proceed screen by screen without relying on hidden assumptions.

Progress rule: when a task in this file is completed, update its checkbox from `[ ]` to `[x]` in the same implementation turn or commit, and keep the `Verify:` line directly below it.

## Status Snapshot (last reviewed 2026-05-11)

| Phase | Done / Total | Status |
|---|---|---|
| F0 - Scaffold + Providers | 8 / 8 | Scaffold, providers, env example, typed API/query/mutation layer, and design fixtures shipped. |
| F1 - AppShell + Provider Status + Navigation | 3 / 4 | Shared AppShell, live provider pills, and desktop sidebar navigation shipped; mobile drawer/provider dialog polish remains. |
| F2 - Projects + GDD Version History | 0 / 4 | List, create, detail, version-history rows. |
| F3 - Run Dashboard | 5 / 5 | Timeline, coverage, agent runs, artifact tabs, design alignment, and hydration fix shipped. |
| F4 - HIL Queues (HIL-0 / 1 / 2 / 3) | 0 / 3 | One route template; tier param drives queue + mutation shape. |
| F5 - Inspection Tables | 0 / 2 | Reusable `<ArtifactTable>` + detail drawer. |
| F6 - Sync Log + Risk Center | 0 / 3 | Sync log, risk grouped table, kill-switch banner. |
| F7 - Sign-Off + Final Report | 0 / 2 | Sign-off button, printable report. |
| F8 - Verification + Submission Polish | 2 / 5 | Lint and build pass; full E2E walkthrough, submission screenshots, and README remain. |

## Next Implementation Slice - Projects + AppShell Polish

The data layer, AppShell, and run dashboard are now in place. Recommended next order:

1. Add the remaining AppShell polish: provider details dialog and mobile sidebar drawer.
2. Build `/projects` list + create dialog from `useProjects()`, `useCreateProject()`, and `useTriggerRun()`.
3. Build `/projects/[project_id]` detail with run history, GDD document history, and DELTA trigger.
4. Verify with `npm run lint`, `npx tsc --noEmit`, and `npm run build`.

After this slice is green, continue with HIL queues and the reusable inspection table extraction.

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

## Phase F1 — AppShell + Provider Status + Navigation

- [x] Task: Port `<AppShell>` into `frontend/src/components/app-shell.tsx` and mount it from `frontend/src/app/layout.tsx`. Header is 56px with provider pills + search; sidebar is 256px with workspace/current-run/settings navigation.
  Verify: Browser check on `/runs/run_87a8f69786fc` shows `header` height `56px`, `aside` width `256px`, and `npm run lint` clean.

- [x] Task: Implement `<ProviderStatusPills>` reading `GET /api/v1/providers/status` via `useProvidersStatus()`; pill colour reflects `credentials_ready`.
  Verify: Browser check on the running backend shows live pills such as `AI openai`, `Notion real`, and `repo supabase`; unavailable credentials render the red pill style.

- [x] Task: Sidebar navigation uses Next.js `<Link>` and active state from `usePathname()` for Projects, Runs, Dashboard, HIL queue, Sync log, Risk, Sign off, and Settings.
  Verify: Current run links are generated from `/runs/<id>` and active items render with indigo/slate styling.

- [ ] Task: Add remaining AppShell polish: provider details dialog and mobile sidebar drawer for viewports `< lg`.
  Verify: Clicking a provider pill opens details; sidebar remains reachable on mobile.

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

- [x] Task: Build `/runs/[run_id]` page with vertical timeline from `GET /api/v1/runs/{run_id}/timeline`; each `StageEvent` rendered as a card with stage name, status, timestamp, message.
  Verify: Snake Escape demo timeline shows 9 stages from `S0_TRIGGER` to `FINAL_COVERAGE`.

- [x] Task: Build coverage cards from `GET /api/v1/runs/{run_id}/coverage`: section counts, feature/task/test-case counts, `risk_summary`, `sync_summary`, `gdd_version_metadata`, `sign_off`.
  Verify: `/runs/run_87a8f69786fc` renders coverage percentage, total/actionable sections, generated artifact counts, risk by severity/code, sync by phase, GDD metadata, and sign-off state.

- [x] Task: Build agent runs panel from `GET /api/v1/runs/{run_id}/agent-runs`. Agent A row exposes `output_snapshot.attempt_count` + `retry_exhausted`; expand button shows the `attempts[]` log.
  Verify: `/runs/run_87a8f69786fc` shows Agent A attempt count/retry state and expandable attempt log.

- [x] Task: Add inspection tabs (Features / Epics / Stories / Tasks / Test Cases / Validation Issues) with route-local table components.
  Verify: All six tabs consume their typed query hooks and render backend payloads; reusable `<ArtifactTable>` extraction remains tracked in Phase F5.

- [x] Task: Align dashboard visual shell with `ui-design/qa-runs-dashboard` and fix invalid HTML hydration warning.
  Verify: Browser check shows Inter font, slate/indigo tokens, AppShell/sidebar/header, and no `<div>`-inside-`<p>` hydration warning.

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

- [x] Task: `npm run lint` clean from `frontend/`.
  Verify: Exit code 0.

- [x] Task: `npm run build` clean from `frontend/`.
  Verify: Exit code 0; `.next/` build output present.

- [ ] Task: Capture six submission screenshots — AppShell with provider pills, Run dashboard with timeline + coverage, HIL-2 queue, Sync log filtered by Sync-B, Risk center, signed-off coverage report. Store under `docs/screenshots/`.
  Verify: All six PNGs exist under `docs/screenshots/` and are linked from `frontend/README.md`.

- [ ] Task: Write `frontend/README.md` documenting `npm install`, `npm run dev`, env variables, and the screenshot capture workflow.
  Verify: A new user can follow the README and reproduce the happy-path demo end-to-end.
