/**
 * Typed `useQuery` hooks covering every GET endpoint exposed by
 * `backend/app/api/v1/routes.py`. Query keys are centralised in
 * `queryKeys` so mutations can invalidate the right slices.
 */

import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

import { api } from "./api";
import type {
  AgentRun,
  CoverageReport,
  Epic,
  Feature,
  GDDDocument,
  GDDSection,
  HealthResponse,
  HIL0Question,
  HIL0Resolution,
  HilTier,
  Project,
  ProvidersStatus,
  QATask,
  ReviewDecision,
  ReviewQueue,
  RiskEvent,
  Run,
  StageEvent,
  Story,
  SyncEvent,
  TestCase,
  ValidationIssue,
} from "./types";

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

/**
 * Build query keys from a small set of helpers so they are stable across
 * call sites and easy to invalidate from `mutations.ts`. The hierarchy
 * mirrors the URL hierarchy of the backend: ["runs", runId, "tasks"] for
 * /runs/{runId}/tasks, etc.
 */
export const queryKeys = {
  health: ["health"] as const,
  providersStatus: ["providers", "status"] as const,
  projects: ["projects"] as const,
  project: (projectId: string) => ["projects", projectId] as const,
  projectGddDocuments: (projectId: string) =>
    ["projects", projectId, "gdd-documents"] as const,
  runs: ["runs"] as const,
  run: (runId: string) => ["runs", runId] as const,
  timeline: (runId: string) => ["runs", runId, "timeline"] as const,
  coverage: (runId: string) => ["runs", runId, "coverage"] as const,
  sections: (runId: string) => ["runs", runId, "sections"] as const,
  hil0Questions: (runId: string) =>
    ["runs", runId, "hil-0", "questions"] as const,
  hil0Resolutions: (runId: string) =>
    ["runs", runId, "hil-0", "resolutions"] as const,
  features: (runId: string) => ["runs", runId, "features"] as const,
  epics: (runId: string) => ["runs", runId, "epics"] as const,
  stories: (runId: string) => ["runs", runId, "stories"] as const,
  tasks: (runId: string) => ["runs", runId, "tasks"] as const,
  testCases: (runId: string) => ["runs", runId, "test-cases"] as const,
  validationIssues: (runId: string) =>
    ["runs", runId, "validation-issues"] as const,
  riskEvents: (runId: string) => ["runs", runId, "risk-events"] as const,
  syncEvents: (runId: string) => ["runs", runId, "sync-events"] as const,
  agentRuns: (runId: string) => ["runs", runId, "agent-runs"] as const,
  reviewDecisions: (runId: string) =>
    ["runs", runId, "review-decisions"] as const,
  reviewQueue: (runId: string, tier: HilTier) =>
    ["runs", runId, "review-queues", tier] as const,
} as const;

// ---------------------------------------------------------------------------
// Hook helpers
// ---------------------------------------------------------------------------

/**
 * Extra react-query options consumers can pass to any hook. Mostly used to
 * disable a query when its ID parameter is empty (enabled: false).
 */
type ExtraOptions<T> = Omit<
  UseQueryOptions<T, Error, T, readonly unknown[]>,
  "queryKey" | "queryFn"
>;

/**
 * Common useQuery wrapper. Named `useBaseQuery` (not `buildQuery`) so the
 * React hooks lint rule recognises it as a hook call site.
 */
function useBaseQuery<T>(
  key: readonly unknown[],
  path: string,
  extra?: ExtraOptions<T>
) {
  return useQuery<T, Error, T, readonly unknown[]>({
    queryKey: key,
    queryFn: ({ signal }) => api<T>(path, { signal }),
    ...extra,
  });
}

// ---------------------------------------------------------------------------
// Global hooks
// ---------------------------------------------------------------------------

export const useHealth = (extra?: ExtraOptions<HealthResponse>) =>
  useBaseQuery<HealthResponse>(queryKeys.health, "/health", extra);

export const useProvidersStatus = (extra?: ExtraOptions<ProvidersStatus>) =>
  useBaseQuery<ProvidersStatus>(
    queryKeys.providersStatus,
    "/providers/status",
    extra
  );

// ---------------------------------------------------------------------------
// Project hooks
// ---------------------------------------------------------------------------

export const useProjects = (extra?: ExtraOptions<Project[]>) =>
  useBaseQuery<Project[]>(queryKeys.projects, "/projects", extra);

export const useProject = (
  projectId: string,
  extra?: ExtraOptions<Project>
) =>
  useBaseQuery<Project>(
    queryKeys.project(projectId),
    `/projects/${projectId}`,
    { enabled: Boolean(projectId), ...extra }
  );

export const useProjectGddDocuments = (
  projectId: string,
  extra?: ExtraOptions<GDDDocument[]>
) =>
  useBaseQuery<GDDDocument[]>(
    queryKeys.projectGddDocuments(projectId),
    `/projects/${projectId}/gdd-documents`,
    { enabled: Boolean(projectId), ...extra }
  );

// ---------------------------------------------------------------------------
// Run-level hooks
// ---------------------------------------------------------------------------

export const useRuns = (extra?: ExtraOptions<Run[]>) =>
  useBaseQuery<Run[]>(queryKeys.runs, "/runs", extra);

export const useRun = (runId: string, extra?: ExtraOptions<Run>) =>
  useBaseQuery<Run>(queryKeys.run(runId), `/runs/${runId}`, {
    enabled: Boolean(runId),
    ...extra,
  });

export const useTimeline = (
  runId: string,
  extra?: ExtraOptions<StageEvent[]>
) =>
  useBaseQuery<StageEvent[]>(
    queryKeys.timeline(runId),
    `/runs/${runId}/timeline`,
    { enabled: Boolean(runId), ...extra }
  );

export const useCoverage = (
  runId: string,
  extra?: ExtraOptions<CoverageReport>
) =>
  useBaseQuery<CoverageReport>(
    queryKeys.coverage(runId),
    `/runs/${runId}/coverage`,
    { enabled: Boolean(runId), ...extra }
  );

export const useSections = (
  runId: string,
  extra?: ExtraOptions<GDDSection[]>
) =>
  useBaseQuery<GDDSection[]>(
    queryKeys.sections(runId),
    `/runs/${runId}/sections`,
    { enabled: Boolean(runId), ...extra }
  );

// ---------------------------------------------------------------------------
// HIL-0
// ---------------------------------------------------------------------------

export const useHil0Questions = (
  runId: string,
  extra?: ExtraOptions<HIL0Question[]>
) =>
  useBaseQuery<HIL0Question[]>(
    queryKeys.hil0Questions(runId),
    `/runs/${runId}/hil-0/questions`,
    { enabled: Boolean(runId), ...extra }
  );

export const useHil0Resolutions = (
  runId: string,
  extra?: ExtraOptions<HIL0Resolution[]>
) =>
  useBaseQuery<HIL0Resolution[]>(
    queryKeys.hil0Resolutions(runId),
    `/runs/${runId}/hil-0/resolutions`,
    { enabled: Boolean(runId), ...extra }
  );

// ---------------------------------------------------------------------------
// Artifact hooks (features / epics / stories / tasks / test cases)
// ---------------------------------------------------------------------------

export const useFeatures = (
  runId: string,
  extra?: ExtraOptions<Feature[]>
) =>
  useBaseQuery<Feature[]>(
    queryKeys.features(runId),
    `/runs/${runId}/features`,
    { enabled: Boolean(runId), ...extra }
  );

export const useEpics = (runId: string, extra?: ExtraOptions<Epic[]>) =>
  useBaseQuery<Epic[]>(queryKeys.epics(runId), `/runs/${runId}/epics`, {
    enabled: Boolean(runId),
    ...extra,
  });

export const useStories = (runId: string, extra?: ExtraOptions<Story[]>) =>
  useBaseQuery<Story[]>(queryKeys.stories(runId), `/runs/${runId}/stories`, {
    enabled: Boolean(runId),
    ...extra,
  });

export const useTasks = (runId: string, extra?: ExtraOptions<QATask[]>) =>
  useBaseQuery<QATask[]>(queryKeys.tasks(runId), `/runs/${runId}/tasks`, {
    enabled: Boolean(runId),
    ...extra,
  });

export const useTestCases = (
  runId: string,
  extra?: ExtraOptions<TestCase[]>
) =>
  useBaseQuery<TestCase[]>(
    queryKeys.testCases(runId),
    `/runs/${runId}/test-cases`,
    { enabled: Boolean(runId), ...extra }
  );

// ---------------------------------------------------------------------------
// Issues / risk / sync / agent runs
// ---------------------------------------------------------------------------

export const useValidationIssues = (
  runId: string,
  extra?: ExtraOptions<ValidationIssue[]>
) =>
  useBaseQuery<ValidationIssue[]>(
    queryKeys.validationIssues(runId),
    `/runs/${runId}/validation-issues`,
    { enabled: Boolean(runId), ...extra }
  );

export const useRiskEvents = (
  runId: string,
  extra?: ExtraOptions<RiskEvent[]>
) =>
  useBaseQuery<RiskEvent[]>(
    queryKeys.riskEvents(runId),
    `/runs/${runId}/risk-events`,
    { enabled: Boolean(runId), ...extra }
  );

export const useSyncEvents = (
  runId: string,
  extra?: ExtraOptions<SyncEvent[]>
) =>
  useBaseQuery<SyncEvent[]>(
    queryKeys.syncEvents(runId),
    `/runs/${runId}/sync-events`,
    { enabled: Boolean(runId), ...extra }
  );

export const useAgentRuns = (
  runId: string,
  extra?: ExtraOptions<AgentRun[]>
) =>
  useBaseQuery<AgentRun[]>(
    queryKeys.agentRuns(runId),
    `/runs/${runId}/agent-runs`,
    { enabled: Boolean(runId), ...extra }
  );

// ---------------------------------------------------------------------------
// Review decisions + review queues
// ---------------------------------------------------------------------------

export const useReviewDecisions = (
  runId: string,
  extra?: ExtraOptions<ReviewDecision[]>
) =>
  useBaseQuery<ReviewDecision[]>(
    queryKeys.reviewDecisions(runId),
    `/runs/${runId}/review-decisions`,
    { enabled: Boolean(runId), ...extra }
  );

export const useReviewQueue = (
  runId: string,
  tier: HilTier,
  extra?: ExtraOptions<ReviewQueue>
) =>
  useBaseQuery<ReviewQueue>(
    queryKeys.reviewQueue(runId, tier),
    `/runs/${runId}/review-queues/${tier}`,
    { enabled: Boolean(runId) && Boolean(tier), ...extra }
  );
