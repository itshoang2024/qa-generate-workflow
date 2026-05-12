"use client";

import { RefreshCw, RotateCcw } from "lucide-react";

import { cn } from "@/lib/utils";
import { useAgentBJobs } from "@/lib/queries";
import { useRetryAgentBJob } from "@/lib/mutations";
import type { AgentBJob, AgentBScope, AgentBJobStatus } from "@/lib/types";

const COLUMNS: Array<{ status: AgentBJobStatus; label: string }> = [
  { status: "QUEUED", label: "Queued" },
  { status: "RUNNING", label: "Running" },
  { status: "SUCCESS", label: "Done" },
  { status: "FAILED", label: "Failed" },
];

export function AgentBJobBoard({
  runId,
  scope,
}: {
  runId: string;
  scope?: AgentBScope;
}) {
  const jobsQuery = useAgentBJobs(runId);
  const retryJob = useRetryAgentBJob(runId);
  const jobs = (jobsQuery.data ?? []).filter((job) => !scope || job.scope_type === scope);
  const failedJobs = jobs.filter((job) => job.status === "FAILED" || job.status === "TIMEOUT");

  const retryAll = async () => {
    for (const job of failedJobs) {
      await retryJob.mutateAsync(job.id);
    }
  };

  if (!jobs.length && !jobsQuery.isPending) {
    return null;
  }

  return (
    <section className="mb-5 rounded-xl border border-border bg-card">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div>
          <h2 className="text-[13.5px] font-semibold text-slate-100">Agent B jobs</h2>
          <p className="mt-0.5 text-[12px] text-slate-500">
            {jobs.length} job(s)
            {scope ? ` - ${scope}` : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => jobsQuery.refetch()}
            className="inline-flex size-8 items-center justify-center rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800"
            aria-label="Refresh Agent B jobs"
          >
            <RefreshCw size={14} />
          </button>
          {failedJobs.length ? (
            <button
              type="button"
              disabled={retryJob.isPending}
              onClick={() => void retryAll()}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-amber-500/15 px-3 text-[12px] font-medium text-amber-300 hover:bg-amber-500/25 disabled:opacity-60"
            >
              <RotateCcw size={13} />
              Retry failed
            </button>
          ) : null}
        </div>
      </div>

      <div className="grid gap-3 p-3 md:grid-cols-4">
        {COLUMNS.map((column) => {
          const columnJobs = jobs.filter((job) =>
            column.status === "FAILED"
              ? job.status === "FAILED" || job.status === "TIMEOUT"
              : job.status === column.status
          );
          return (
            <div key={column.status} className="min-h-28 rounded-lg border border-border bg-slate-950/25">
              <div className="flex items-center justify-between border-b border-border px-3 py-2">
                <span className="text-[11px] font-medium uppercase tracking-[0.06em] text-slate-500">
                  {column.label}
                </span>
                <span className="font-mono text-[11px] text-slate-500">{columnJobs.length}</span>
              </div>
              <div className="space-y-2 p-2">
                {columnJobs.map((job) => (
                  <JobCard
                    key={job.id}
                    job={job}
                    retrying={retryJob.isPending}
                    onRetry={() => retryJob.mutate(job.id)}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function JobCard({
  job,
  retrying,
  onRetry,
}: {
  job: AgentBJob;
  retrying: boolean;
  onRetry: () => void;
}) {
  const failed = job.status === "FAILED" || job.status === "TIMEOUT";
  return (
    <div
      className={cn(
        "rounded-md border px-2.5 py-2 text-[12px]",
        failed ? "border-rose-500/30 bg-rose-500/8" : "border-border bg-card"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="font-mono text-[11px] text-slate-400">{job.scope_id}</div>
          <div className="mt-1 text-slate-500">
            {job.scope_type} - attempt {job.attempt_count}
          </div>
        </div>
        {failed ? (
          <button
            type="button"
            disabled={retrying}
            onClick={onRetry}
            className="inline-flex size-7 shrink-0 items-center justify-center rounded-md bg-rose-500/15 text-rose-300 hover:bg-rose-500/25 disabled:opacity-60"
            aria-label={`Retry ${job.scope_id}`}
          >
            <RotateCcw size={13} />
          </button>
        ) : null}
      </div>
      {job.error_message ? (
        <p className="mt-2 line-clamp-2 text-[11.5px] text-rose-300">{job.error_message}</p>
      ) : null}
    </div>
  );
}
