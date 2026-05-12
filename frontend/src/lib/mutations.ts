/**
 * Typed `useMutation` hooks for every state-changing endpoint exposed by
 * `backend/app/api/v1/routes.py`. Each mutation:
 *
 * - Validates input through the matching request type from `./types`.
 * - Invalidates the affected query keys on success so screens reflect the
 *   mutation without manual refetching.
 * - Surfaces success / failure through Sonner toasts.
 */

import {
  useMutation,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError } from "./api";
import { queryKeys } from "./queries";
import type {
  AgentBJob,
  AgentBStageResponse,
  DemoRunRequest,
  Epic,
  EpicMergeRequest,
  EpicPatchRequest,
  EpicSplitRequest,
  HIL0BulkResolutionRequest,
  HIL0Resolution,
  HIL0ResolutionRequest,
  LoadContextRequest,
  LoadContextResponse,
  Project,
  ProjectCreateRequest,
  ReviewDecision,
  ReviewDecisionRequest,
  Run,
  SignOffRequest,
  SyncReplayResponse,
  TriggerRunRequest,
  TriggerRunResponse,
} from "./types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type MutationExtras<TData, TVariables> = Omit<
  UseMutationOptions<TData, ApiError, TVariables>,
  "mutationFn"
>;

/**
 * Wrap react-query's `useMutation` with a thin error-toast helper. Callers
 * can still pass their own `onSuccess` / `onError` via `extras`; those run
 * after the default toast so they don't have to re-implement the failure
 * path. Returning a `Promise.reject` from `onError` is not needed.
 */
function withErrorToast<TData, TVariables>(
  defaultMessage: string,
  extras?: MutationExtras<TData, TVariables>
): MutationExtras<TData, TVariables> {
  return {
    ...extras,
    onError: (error, variables, onMutateResult, context) => {
      const message =
        error instanceof ApiError
          ? apiErrorDescription(error)
          : (error as Error).message || defaultMessage;
      toast.error(defaultMessage, { description: message });
      extras?.onError?.(error, variables, onMutateResult, context);
    },
  };
}

function apiErrorDescription(error: ApiError): string {
  if (error.code === "hil_gate_blocked" && isRecord(error.details)) {
    const tier = error.details.tier ?? "HIL gate";
    const count = error.details.pending_count ?? "some";
    return `${tier} is still waiting on ${count} review item(s).`;
  }
  if (error.code === "wrong_stage" && isRecord(error.details)) {
    return `Run is at ${error.details.current_stage}; expected ${error.details.expected_stage}.`;
  }
  return `${error.code}: ${error.message}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function invalidateRunSurfaces(
  queryClient: ReturnType<typeof useQueryClient>,
  runId: string
) {
  queryClient.invalidateQueries({ queryKey: queryKeys.run(runId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.runs });
  queryClient.invalidateQueries({ queryKey: queryKeys.timeline(runId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.coverage(runId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.sections(runId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.features(runId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.epics(runId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.stories(runId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.tasks(runId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.testCases(runId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.validationIssues(runId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.agentRuns(runId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.agentBJobs(runId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.syncEvents(runId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.riskEvents(runId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.reviewDecisions(runId) });
  (["HIL-0", "HIL-1", "HIL-2", "HIL-3"] as const).forEach((tier) =>
    queryClient.invalidateQueries({
      queryKey: queryKeys.reviewQueue(runId, tier),
    })
  );
}

// ---------------------------------------------------------------------------
// Project + run creation
// ---------------------------------------------------------------------------

/** `POST /api/v1/projects` — create a new project. */
export function useCreateProject(
  extras?: MutationExtras<Project, ProjectCreateRequest>
) {
  const queryClient = useQueryClient();
  return useMutation<Project, ApiError, ProjectCreateRequest>({
    mutationFn: (body) => api<Project>("/projects", { method: "POST", body }),
    ...withErrorToast("Failed to create project.", extras),
    onSuccess: (project, variables, onMutateResult, context) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects });
      queryClient.setQueryData(queryKeys.project(project.id), project);
      toast.success("Project created", { description: project.name });
      extras?.onSuccess?.(project, variables, onMutateResult, context);
    },
  });
}

/**
 * `POST /api/v1/runs/trigger` — S0 trigger. Exactly one of `project_id`
 * or `project_name` must be supplied. Backend returns the new run id +
 * derived mode (`NEW_GAME` for new project, `DELTA` for existing).
 */
export function useTriggerRun(
  extras?: MutationExtras<TriggerRunResponse, TriggerRunRequest>
) {
  const queryClient = useQueryClient();
  return useMutation<TriggerRunResponse, ApiError, TriggerRunRequest>({
    mutationFn: (body) =>
      api<TriggerRunResponse>("/runs/trigger", { method: "POST", body }),
    ...withErrorToast("Failed to trigger run.", extras),
    onSuccess: (result, variables, onMutateResult, context) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runs });
      queryClient.invalidateQueries({
        queryKey: queryKeys.project(result.project_id),
      });
      toast.success(`Triggered ${result.mode} run`, {
        description: `Run ${result.run_id} for project ${result.project_id}.`,
      });
      extras?.onSuccess?.(result, variables, onMutateResult, context);
    },
  });
}

/**
 * `POST /api/v1/runs/{run_id}/context` — S1 context loader. Parses + versions
 * the uploaded GDD, generates HIL-0 questions, builds the DELTA report.
 */
export function useLoadContext(
  runId: string,
  extras?: MutationExtras<LoadContextResponse, LoadContextRequest | undefined>
) {
  const queryClient = useQueryClient();
  return useMutation<
    LoadContextResponse,
    ApiError,
    LoadContextRequest | undefined
  >({
    mutationFn: (body) =>
      api<LoadContextResponse>(`/runs/${runId}/context`, {
        method: "POST",
        body: body ?? {},
      }),
    ...withErrorToast("Failed to load run context.", extras),
    onSuccess: (result, variables, onMutateResult, context) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.run(runId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.runs });
      queryClient.invalidateQueries({ queryKey: queryKeys.timeline(runId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.coverage(runId) });
      queryClient.invalidateQueries({
        queryKey: queryKeys.projectGddDocuments(result.project_id),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.hil0Questions(runId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.sections(runId) });
      toast.success("Context loaded", {
        description: `Registered ${result.gdd_document.version_id} with ${result.section_count} sections.`,
      });
      extras?.onSuccess?.(result, variables, onMutateResult, context);
    },
  });
}

function useAdvanceRunStage(
  runId: string,
  path: string,
  successTitle: string,
  extras?: MutationExtras<Run, void>
) {
  const queryClient = useQueryClient();
  return useMutation<Run, ApiError, void>({
    mutationFn: () => api<Run>(path, { method: "POST" }),
    ...withErrorToast(`${successTitle} failed.`, extras),
    onSuccess: (run, variables, onMutateResult, context) => {
      queryClient.setQueryData(queryKeys.run(runId), run);
      invalidateRunSurfaces(queryClient, runId);
      toast.success(successTitle, {
        description: `Run advanced to ${run.current_stage}.`,
      });
      extras?.onSuccess?.(run, variables, onMutateResult, context);
    },
  });
}

/** `POST /api/v1/runs/{run_id}/agent-a` — run Agent A + Validation A. */
export function useRunAgentA(runId: string, extras?: MutationExtras<Run, void>) {
  return useAdvanceRunStage(
    runId,
    `/runs/${runId}/agent-a`,
    "Agent A completed",
    extras
  );
}

/** `POST /api/v1/runs/{run_id}/agent-b` — run Agent B + Validation B + Sync-A/B. */
export function useRunAgentB(runId: string, extras?: MutationExtras<Run, void>) {
  return useAdvanceRunStage(
    runId,
    `/runs/${runId}/agent-b`,
    "Agent B completed",
    extras
  );
}

/** `POST /api/v1/runs/{run_id}/agent-c` — run Agent C + Validation C + Sync-C. */
function useAdvanceAgentBSubstage(
  runId: string,
  path: string,
  successTitle: string,
  extras?: MutationExtras<AgentBStageResponse, void>
) {
  const queryClient = useQueryClient();
  return useMutation<AgentBStageResponse, ApiError, void>({
    mutationFn: () => api<AgentBStageResponse>(path, { method: "POST" }),
    ...withErrorToast(`${successTitle} failed.`, extras),
    onSuccess: (result, variables, onMutateResult, context) => {
      queryClient.setQueryData(queryKeys.run(runId), result.run);
      invalidateRunSurfaces(queryClient, runId);
      toast.success(successTitle, {
        description: `Run advanced to ${result.run.current_stage}.`,
      });
      extras?.onSuccess?.(result, variables, onMutateResult, context);
    },
  });
}

export function useRunAgentBEpics(
  runId: string,
  extras?: MutationExtras<AgentBStageResponse, void>
) {
  return useAdvanceAgentBSubstage(
    runId,
    `/runs/${runId}/agent-b/epics`,
    "Agent B epics completed",
    extras
  );
}

export function useRunAgentBStories(
  runId: string,
  extras?: MutationExtras<AgentBStageResponse, void>
) {
  return useAdvanceAgentBSubstage(
    runId,
    `/runs/${runId}/agent-b/stories`,
    "Agent B stories completed",
    extras
  );
}

export function useRunAgentBTasks(
  runId: string,
  extras?: MutationExtras<AgentBStageResponse, void>
) {
  return useAdvanceAgentBSubstage(
    runId,
    `/runs/${runId}/agent-b/tasks`,
    "Agent B tasks completed",
    extras
  );
}

export function useRunAgentC(runId: string, extras?: MutationExtras<Run, void>) {
  return useAdvanceRunStage(
    runId,
    `/runs/${runId}/agent-c`,
    "Agent C completed",
    extras
  );
}

/** `POST /api/v1/runs/{run_id}/finalize` — build final coverage and complete run. */
export function useFinalizeRun(runId: string, extras?: MutationExtras<Run, void>) {
  return useAdvanceRunStage(
    runId,
    `/runs/${runId}/finalize`,
    "Run finalized",
    extras
  );
}

/**
 * `POST /api/v1/demo-runs` — fire the full Snake Escape pipeline end-to-end.
 * Returns the completed `Run` with timeline + coverage populated.
 */
export function useCreateDemoRun(
  extras?: MutationExtras<Run, DemoRunRequest | undefined>
) {
  const queryClient = useQueryClient();
  return useMutation<Run, ApiError, DemoRunRequest | undefined>({
    mutationFn: (body) =>
      api<Run>("/demo-runs", {
        method: "POST",
        body: body ?? { preset: "snake_escape", auto_approve: true },
      }),
    ...withErrorToast("Demo run failed.", extras),
    onSuccess: (run, variables, onMutateResult, context) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runs });
      queryClient.setQueryData(queryKeys.run(run.id), run);
      toast.success("Demo run completed", {
        description: `Run ${run.id} finished with status ${run.status}.`,
      });
      extras?.onSuccess?.(run, variables, onMutateResult, context);
    },
  });
}

// ---------------------------------------------------------------------------
// HIL-0 resolution + HIL-1/2/3 review decisions
// ---------------------------------------------------------------------------

/**
 * `POST /api/v1/runs/{run_id}/hil-0/resolutions` — resolve a single HIL-0
 * clarification question. The backend marks the question as RESOLVED and
 * records the action (`provide_artifact` / `proceed_with_flag` /
 * `skip_section`).
 */
export function useResolveHil0Question(
  runId: string,
  extras?: MutationExtras<HIL0Resolution, HIL0ResolutionRequest>
) {
  const queryClient = useQueryClient();
  return useMutation<HIL0Resolution, ApiError, HIL0ResolutionRequest>({
    mutationFn: (body) =>
      api<HIL0Resolution>(`/runs/${runId}/hil-0/resolutions`, {
        method: "POST",
        body,
      }),
    ...withErrorToast("Failed to resolve HIL-0 question.", extras),
    onSuccess: (resolution, variables, onMutateResult, context) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.hil0Questions(runId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.hil0Resolutions(runId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.reviewQueue(runId, "HIL-0"),
      });
      toast.success("HIL-0 resolved", {
        description: `Question ${resolution.question_id} → ${resolution.action}.`,
      });
      extras?.onSuccess?.(resolution, variables, onMutateResult, context);
    },
  });
}

/**
 * `POST /api/v1/runs/{run_id}/hil-0/resolutions/bulk` — resolve multiple
 * HIL-0 clarification questions in one backend request.
 */
export function useResolveHil0Questions(
  runId: string,
  extras?: MutationExtras<HIL0Resolution[], HIL0BulkResolutionRequest>
) {
  const queryClient = useQueryClient();
  return useMutation<HIL0Resolution[], ApiError, HIL0BulkResolutionRequest>({
    mutationFn: (body) =>
      api<HIL0Resolution[]>(`/runs/${runId}/hil-0/resolutions/bulk`, {
        method: "POST",
        body,
      }),
    ...withErrorToast("Failed to resolve HIL-0 questions.", extras),
    onSuccess: (resolutions, variables, onMutateResult, context) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.hil0Questions(runId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.hil0Resolutions(runId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.reviewQueue(runId, "HIL-0"),
      });
      toast.success("HIL-0 resolved", {
        description: `${resolutions.length} question(s) marked proceed with flag.`,
      });
      extras?.onSuccess?.(resolutions, variables, onMutateResult, context);
    },
  });
}

/**
 * `POST /api/v1/review-decisions` — generic HIL-1 / HIL-2 / HIL-3 decision.
 * The backend cascades epic decisions to features and stories automatically.
 */
export function useCreateReviewDecision(
  extras?: MutationExtras<ReviewDecision, ReviewDecisionRequest>
) {
  const queryClient = useQueryClient();
  return useMutation<ReviewDecision, ApiError, ReviewDecisionRequest>({
    mutationFn: (body) =>
      api<ReviewDecision>("/review-decisions", { method: "POST", body }),
    ...withErrorToast("Failed to record review decision.", extras),
    onSuccess: (decision, variables, onMutateResult, context) => {
      const runId = decision.run_id;
      // The decision can change lanes on features / epics / stories / tasks
      // / test cases — invalidate generously so every tab refreshes.
      queryClient.invalidateQueries({
        queryKey: queryKeys.reviewDecisions(runId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.features(runId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.epics(runId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.stories(runId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks(runId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.testCases(runId) });
      // All HIL queues read from the same artifacts so any could drop the
      // newly-approved item — invalidate all four tiers.
      (["HIL-0", "HIL-1", "HIL-2", "HIL-3"] as const).forEach((tier) =>
        queryClient.invalidateQueries({
          queryKey: queryKeys.reviewQueue(runId, tier),
        })
      );
      toast.success("Review decision recorded", {
        description: `${decision.target_type} ${decision.target_id} → ${decision.decision}.`,
      });
      extras?.onSuccess?.(decision, variables, onMutateResult, context);
    },
  });
}

// ---------------------------------------------------------------------------
// Agent B hierarchical jobs + epic editing
// ---------------------------------------------------------------------------

export function useRetryAgentBJob(
  runId: string,
  extras?: MutationExtras<AgentBJob, string>
) {
  const queryClient = useQueryClient();
  return useMutation<AgentBJob, ApiError, string>({
    mutationFn: (jobId) =>
      api<AgentBJob>(`/runs/${runId}/agent-b/jobs/${jobId}/retry`, {
        method: "POST",
        body: {},
      }),
    ...withErrorToast("Agent B retry failed.", extras),
    onSuccess: (job, variables, onMutateResult, context) => {
      invalidateRunSurfaces(queryClient, runId);
      toast.success("Agent B job retried", {
        description: `${job.scope_type} ${job.scope_id} is ${job.status}.`,
      });
      extras?.onSuccess?.(job, variables, onMutateResult, context);
    },
  });
}

export function useUpdateEpic(
  runId: string,
  extras?: MutationExtras<Epic, { epicId: string; body: EpicPatchRequest }>
) {
  const queryClient = useQueryClient();
  return useMutation<Epic, ApiError, { epicId: string; body: EpicPatchRequest }>({
    mutationFn: ({ epicId, body }) =>
      api<Epic>(`/runs/${runId}/epics/${epicId}`, { method: "PATCH", body }),
    ...withErrorToast("Epic update failed.", extras),
    onSuccess: (epic, variables, onMutateResult, context) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.epics(runId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.run(runId) });
      toast.success("Epic updated", { description: epic.title });
      extras?.onSuccess?.(epic, variables, onMutateResult, context);
    },
  });
}

export function useMergeEpics(
  runId: string,
  extras?: MutationExtras<Epic, EpicMergeRequest>
) {
  const queryClient = useQueryClient();
  return useMutation<Epic, ApiError, EpicMergeRequest>({
    mutationFn: (body) =>
      api<Epic>(`/runs/${runId}/epics/merge`, { method: "POST", body }),
    ...withErrorToast("Epic merge failed.", extras),
    onSuccess: (epic, variables, onMutateResult, context) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.epics(runId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.run(runId) });
      toast.success("Epics merged", { description: epic.title });
      extras?.onSuccess?.(epic, variables, onMutateResult, context);
    },
  });
}

export function useSplitEpic(
  runId: string,
  extras?: MutationExtras<Epic[], EpicSplitRequest>
) {
  const queryClient = useQueryClient();
  return useMutation<Epic[], ApiError, EpicSplitRequest>({
    mutationFn: (body) =>
      api<Epic[]>(`/runs/${runId}/epics/split`, { method: "POST", body }),
    ...withErrorToast("Epic split failed.", extras),
    onSuccess: (epics, variables, onMutateResult, context) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.epics(runId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.run(runId) });
      toast.success("Epic split", { description: `${epics.length} epics created.` });
      extras?.onSuccess?.(epics, variables, onMutateResult, context);
    },
  });
}

// ---------------------------------------------------------------------------
// Sync replay + sign-off
// ---------------------------------------------------------------------------

/**
 * `POST /api/v1/runs/{run_id}/sync-replay` — replay every sync event still
 * in `FAILED` status. Currently the mock backend never produces FAILED
 * events, so this is mostly a placeholder until the real Notion adapter
 * lands; the UI surface is kept now so the screen does not need to change
 * when failures start happening.
 */
export function useReplaySync(
  runId: string,
  extras?: MutationExtras<SyncReplayResponse, void>
) {
  const queryClient = useQueryClient();
  return useMutation<SyncReplayResponse, ApiError, void>({
    mutationFn: () =>
      api<SyncReplayResponse>(`/runs/${runId}/sync-replay`, {
        method: "POST",
      }),
    ...withErrorToast("Failed to replay sync events.", extras),
    onSuccess: (result, variables, onMutateResult, context) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.syncEvents(runId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.coverage(runId) });
      toast.success("Sync replay complete", {
        description: `${result.replayed_count} event(s) replayed.`,
      });
      extras?.onSuccess?.(result, variables, onMutateResult, context);
    },
  });
}

/**
 * `POST /api/v1/runs/{run_id}/sign-off` — record QA Lead sign-off. Updates
 * `Run.signed_off_by` / `signed_off_at` and the coverage report's
 * `sign_off` block.
 */
export function useSignOffRun(
  runId: string,
  extras?: MutationExtras<Run, SignOffRequest>
) {
  const queryClient = useQueryClient();
  return useMutation<Run, ApiError, SignOffRequest>({
    mutationFn: (body) =>
      api<Run>(`/runs/${runId}/sign-off`, { method: "POST", body }),
    ...withErrorToast("Sign-off failed.", extras),
    onSuccess: (run, variables, onMutateResult, context) => {
      queryClient.setQueryData(queryKeys.run(runId), run);
      queryClient.invalidateQueries({ queryKey: queryKeys.coverage(runId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.runs });
      toast.success("Run signed off", {
        description: `${run.signed_off_by} at ${run.signed_off_at}.`,
      });
      extras?.onSuccess?.(run, variables, onMutateResult, context);
    },
  });
}
