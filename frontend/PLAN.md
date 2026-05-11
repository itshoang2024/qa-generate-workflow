# Frontend Completion Plan

## Goal

Deliver a Next.js demo app that exposes every Task-1..4 capability already implemented in the backend to a reviewer who has never seen the codebase. The frontend consumes only `/api/v1` endpoints, follows the four root source-of-truth solution files for what state to surface, and uses the shadcn-flavoured slate/indigo design system seeded in `frontend/_design_fixtures/design-system.md`. The visual work is produced in Claude Design and ported into the repo via the Claude Code handoff; this plan covers the surrounding plumbing and per-screen acceptance.

The frontend is the last credibility gap before submission: backend is feature-complete in mock mode (S0..S7 + HIL-0..HIL-3 + Sync-A/B/C + RiskEvent + kill switch + sign-off), but a reviewer currently cannot see it without `curl`.

## Current State (2026-05-11)

Already shipped:

- Next.js 16 App Router project scaffolded under `frontend/` with TypeScript, Tailwind, ESLint, and `src/` directory layout.
- Dependencies installed: `@tanstack/react-query` + devtools, `next-themes`, `sonner`, `lucide-react`, `react-hook-form` + `@hookform/resolvers`, `zod`, `clsx`, `tailwind-merge`, `class-variance-authority`.
- shadcn/ui primitives added: button, card, badge, table, tabs, dialog, input, input-group, select, textarea, separator, skeleton, sonner, dropdown-menu, sheet, command.
- `src/app/providers.tsx` wraps `QueryClientProvider` (singleton browser client + per-request SSR client), `ThemeProvider` (default `dark`, attribute `class`), Sonner `<Toaster>` (bottom-right, richColors), and `<ReactQueryDevtools>` (dev-only, bottom-left).
- `src/app/layout.tsx` mounts `<Providers>` and the shared `<AppShell>` around all routes with `suppressHydrationWarning` on `<html>` and an updated `<Metadata>` title/description.
- `src/lib/types.ts`, `src/lib/api.ts`, `src/lib/queries.ts`, and `src/lib/mutations.ts` cover the backend `/api/v1` read and mutation surface with typed React Query hooks.
- `frontend/.env.local.example` documents `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000/api/v1`; local `.env.local` uses the same value.
- `frontend/_design_fixtures/` contains 17 representative JSON payloads plus `design-system.md` for design handoff/reference work.
- `src/components/app-shell.tsx` implements the shared dark slate AppShell: 256px desktop sidebar, mobile sidebar drawer, 56px header, provider status pills/details dialog from `/providers/status`, search command shell, current-run navigation, and user footer.
- `/projects` and `/projects/[project_id]` are implemented with project listing, new project dialog, run history, DELTA trigger, and GDD version history from `/projects/{project_id}/gdd-documents`.
- `/runs/[run_id]` is implemented in `src/app/runs/[id]/page.tsx` with agent runs, timeline, coverage cards, artifact tabs, loading/error/empty states, and design-token alignment with `ui-design/qa-runs-dashboard`.
- The run dashboard hydration issue caused by a `<div>` skeleton inside `<p>` was fixed with an inline `<span>` skeleton.

Still missing:

- `/runs/[run_id]/hil/[tier]`, `/runs/[run_id]/sync-log`, `/runs/[run_id]/risk`, and `/runs/[run_id]/sign-off`.
- Reusable `<ArtifactTable>` and `<ArtifactDetailDrawer>` extraction. The run dashboard currently uses route-local table components.
- Global header sign-off action polish.
- `frontend/README.md` with run + build commands.

## Target Architecture

```text
Next.js 16 App Router (src/app)
    │
    ├── layout.tsx ─── Providers (QueryClient + Theme + Toaster + Devtools)
    │       └── AppShell (header + sidebar + provider pills + search)
    │
    ├── projects/                 → list + create dialog
    │   └── [project_id]/         → GDD version history + trigger run + run list
    │
    ├── runs/[run_id]/
    │   ├── page.tsx              → dashboard: timeline + coverage + agent runs + tabs
    │   ├── hil/[tier]/page.tsx   → HIL-0/HIL-1/HIL-2/HIL-3 review queue
    │   ├── sync-log/page.tsx     → sync events filtered by sync_phase
    │   ├── risk/page.tsx         → risk events + kill switch state
    │   └── sign-off/page.tsx     → coverage summary + sign-off action
    │
    └── lib/
        ├── api.ts                → envelope-aware fetch wrapper
        ├── queries.ts            → typed useQuery hooks + queryKeys
        ├── mutations.ts          → typed useMutation hooks + cache invalidation
        └── types.ts              → mirror of backend domain models (manual sync)
```

Architecture rules:

- The frontend never reads Supabase directly. Every read goes through `/api/v1`.
- All responses pass through `api<T>(path)` which throws on `error` and returns `data`.
- React Query owns server state; only ephemeral UI state lives in React local state. No Zustand / Redux.
- All mutations invalidate the relevant query keys on success so screens stay consistent without polling.
- Pages stay route-based (App Router); shared composition lives in `src/components/`.
- Visual work is generated in Claude Design with the linked `frontend/` subdirectory; ported into the repo via "Handoff to Claude Code → local agent" then wired to `lib/queries.ts` / `lib/mutations.ts`.
- Backend types are mirrored manually in `lib/types.ts`; no OpenAPI codegen yet — keep the surface small enough to maintain by hand.

## Per-Screen Plan

### Screen 1 — AppShell + Provider Status + Navigation

Surfaces: every page. Built first because all other screens nest inside it.

Behaviour:

- Top header (56px): provider pills from `GET /api/v1/providers/status` (AI / Notion / Repository with `credentials_ready` colour) and a search command shell.
- Left sidebar (256px): Projects, Runs, Current run dashboard, HIL queue, Sync log, Risk, Sign off, Settings, and the QA Lead footer.
- Dark mode default with light toggle in the user menu (Sonner inherits theme via `useTheme()`).

Acceptance:

- AppShell renders on every route through `src/app/layout.tsx`.
- Provider pills show the live provider/credentials state from `/providers/status`.
- Clicking a provider pill opens a details dialog with provider, readiness, and API base.
- Sidebar links use Next.js `<Link>` with active state from `usePathname()`.
- Mobile viewports keep navigation reachable through the sidebar drawer.
- Remaining polish: optional global sign-off action.

### Screen 2 — Projects + GDD version history

Surfaces: `/projects`, `/projects/[project_id]`.

Behaviour:

- List from `GET /api/v1/projects`.
- "New project" dialog exposes a create-record action via `POST /api/v1/projects` and a primary create+trigger action via `POST /api/v1/runs/trigger` with `project_name` for backend-owned `NEW_GAME` creation.
- Existing project picker drives `POST /api/v1/runs/trigger` with `project_id` → mode `DELTA`.
- Project detail page shows runs scoped to the project + GDD version history from `GET /api/v1/projects/{project_id}/gdd-documents` with `parent_document_id` chain and `description_status` badges (`PENDING` / `USER_PROVIDED` / `AI_GENERATED`).

Acceptance:

- New project → `mode=NEW_GAME` run; existing project → `mode=DELTA` run.
- Uploading the second GDD for a project shows `v2` linked to `v1` via parent badge.
- Trigger button states reflect mutation `isPending` and toast on success/error.

### Screen 3 — Run dashboard

Surfaces: `/runs/[run_id]`.

Behaviour:

- Vertical timeline from `GET /api/v1/runs/{run_id}/timeline` showing every `StageEvent` S0..FINAL_COVERAGE with status + message.
- Coverage cards from `GET /api/v1/runs/{run_id}/coverage`: section counts, feature/task/test-case counts, `risk_summary` (by severity + by code), `sync_summary` (by status + by phase), `gdd_version_metadata`, `sign_off` block.
- Agent runs panel from `GET /api/v1/runs/{run_id}/agent-runs` with Agent A's `attempt_count`, `retry_exhausted`, and expandable `attempts[]` log from the input/output snapshots.
- Tabs below: Features, Epics, Stories, Tasks, Test Cases, Validation Issues. The current implementation uses route-local tables; Screen 5 remains responsible for extracting a reusable inspection table and drawer.

Acceptance:

- Demo run shows timeline with 9 stage events (S0 → FINAL_COVERAGE).
- Coverage cards show the live backend coverage payload, including section counts, generated artifact counts, risk summary, sync summary, GDD metadata, and sign-off state.
- Agent A row exposes attempt log when expanded.
- `npm run lint`, `npx tsc --noEmit`, and `npm run build` pass after the dashboard/AppShell implementation.

### Screen 4 — HIL queues (tiers 0/1/2/3)

Surfaces: `/runs/[run_id]/hil/[tier]`.

Behaviour:

- Reads `GET /api/v1/runs/{run_id}/review-queues/{HIL-tier}`; renders the API's pre-grouped `ReviewQueueGroup[]` (group by reviewer / feature / epic).
- HIL-0 actions: `POST /api/v1/runs/{run_id}/hil-0/resolutions` with `action` in `{provide_artifact, proceed_with_flag, skip_section}`. Form per question.
- HIL-1/2/3 actions: `POST /api/v1/review-decisions` with `target_type` + `target_id` + `decision` in `{APPROVED, REJECTED, BLOCKED}` + optional `comment` and `patch`.
- Lane badges (AUTO / BATCH / BLOCK) match `ReviewQueueItem.lane`; severity badges on associated validation issues.
- Bulk approve at group level → fan out into individual mutations + single toast.

Acceptance:

- Approving a BATCH-lane task at HIL-2 flips its `lane` to AUTO and removes it from the queue (mirrors `test_review_decision_approval_updates_lane_and_removes_item_from_queue`).
- HIL-0 resolution updates question `status` to `RESOLVED` and the queue removes it.
- Empty state for each tier when no items are pending review.

### Screen 5 — Inspection tables (Features / Epics / Stories / Tasks / Test Cases / Validation Issues)

Surfaces: tabs inside `/runs/[run_id]` (Screen 3) plus reusable component.

Behaviour:

- Single `<ArtifactTable>` accepts column definitions per artifact type.
- Common columns: target_id (monospace chip), title, lane badge, review_status badge, source_sections (chip list), confidence (sparkbar) where applicable.
- Feature column extras: `delta_status` badge (`NEW` / `MODIFIED` / `UNCHANGED` / `REMOVED`), cross-cutting flag.
- Task column extras: assignee chip, priority, estimate, `status` (`Ready for Test Cases` vs `Test Cases Ready`).
- Test case column extras: `category` badge, `type`, related task chip.
- Validation issue column extras: severity badge (S1/S2/S3), code, stage.
- Detail drawer (shadcn `<Sheet>`) on row click shows the full Pydantic payload pretty-printed and any related artifacts.

Acceptance:

- Tables paginate (or virtualize) past 20 rows; demo run with 44 test cases stays responsive.
- Sort by lane, severity, or assignee works without round-tripping the server.
- Drawer renders the same fields seen in `GET /api/v1/runs/{run_id}/{artifact_type}`.

### Screen 6 — Sync log + Risk center

Surfaces: `/runs/[run_id]/sync-log`, `/runs/[run_id]/risk`.

Behaviour:

- Sync log: filter pills by `payload.sync_phase` (`Sync-A` / `Sync-B` / `Sync-C`); table columns include `external_id`, `notion_page_id`, `target_type`, `action`, `status`, `retry_count`. Replay action calls `POST /api/v1/runs/{run_id}/sync-replay`.
- Risk center: kill-switch banner at the top if `coverage.risk_summary.by_severity.S1 >= 3` or the run failed with code `kill_switch_tripped`; grouped table by severity (S1 / S2 / S3) showing `code`, `summary`, `target_type`, `target_id`, `owner_action`.

Acceptance:

- Snake Escape demo shows 10 Sync-A + 9 Sync-B + 36 Sync-C events (matching `test_sync_events_endpoint_shows_sync_a_b_c_phases`).
- Risk center shows the `uncovered_actionable_section` events emitted by validators.
- Kill-switch banner appears with a fixture that fakes S1 hallucination ≥ 3.

### Screen 7 — Sign-off + Final report

Surfaces: `/runs/[run_id]/sign-off`.

Behaviour:

- One-page printable summary: coverage payload + sign-off block.
- Primary action: `POST /api/v1/runs/{run_id}/sign-off` with `reviewer` from local profile.
- Button disabled when `run.status !== COMPLETED` or `coverage.risk_summary.by_severity.S1 >= 3` (kill switch).
- After sign-off: green banner with `signed_off_by` + `signed_off_at`.

Acceptance:

- Sign-off mutation updates both the run object and `coverage_report.sign_off` (mirrors `test_sign_off_endpoint_updates_run_and_coverage_report`).
- The page can be printed (`@media print` stylesheet hides chrome, keeps the report).
- Kill-switch state disables the button with an explanatory tooltip.

## Cross-Cutting Requirements

- Every page handles three states: pending (Skeleton), error (inline banner with retry), empty (centred icon + headline + CTA).
- Every mutation toasts success/error via Sonner and invalidates the relevant query keys.
- Every monospace identifier (run_id, feat_*, task_*, external_id, notion_page_id) uses `font-mono text-xs text-slate-400` for visual consistency.
- Dark mode is the default; light mode must work for all screens.
- All routes work offline against a mock backend; no env-flag fallbacks scattered through components.
- No `localStorage` or `sessionStorage` use — keep state ephemeral or server-owned.

## Acceptance Criteria

The frontend slice is complete when:

- `npm run dev` from `frontend/` opens `http://localhost:3000` against `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000/api/v1` and renders the AppShell.
- A new user can: create a project → upload a GDD → trigger NEW_GAME run → walk through HIL-0..HIL-3 → approve at least one task → see Sync-A/B/C in the sync log → see risk events → sign off → see the green sign-off banner on the coverage report.
- A second run on the same project triggers DELTA mode and the GDD version history shows `v1` and `v2` linked by `parent_document_id`.
- `npm run lint` passes from `frontend/`.
- `npm run build` passes from `frontend/`.
- Six submission screenshots are captured: AppShell with provider pills, Run dashboard with timeline + coverage, HIL-2 queue, Sync log filtered by Sync-B, Risk center, signed-off coverage report.
- `frontend/README.md` documents the dev + build + screenshot capture commands.
