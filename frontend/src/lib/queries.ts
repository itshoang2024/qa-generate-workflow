import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export const queryKeys = {
  providersStatus: ["providers-status"] as const,
  projects: ["projects"] as const,
  project: (id: string) => ["projects", id] as const,
  projectGdds: (id: string) => ["projects", id, "gdd-documents"] as const,
  run: (id: string) => ["runs", id] as const,
  coverage: (id: string) => ["runs", id, "coverage"] as const,
  // ... tasks, features, epics, stories, test-cases, risk-events, sync-events, agent-runs, review-queue per tier
};

export const useCoverage = (runId: string) =>
  useQuery({ queryKey: queryKeys.coverage(runId), queryFn: () => api(`/runs/${runId}/coverage`) });