"use client";

import { useMemo } from "react";
import { useParams } from "next/navigation";
import { FileClock, Workflow } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { useProject, useProjectGddDocuments, useRuns } from "@/lib/queries";
import {
  DeltaRunDialog,
  EmptyPanel,
  GddVersionHistory,
  ProjectHeader,
  ProjectMetricGrid,
  ProjectRunTable,
} from "../_components";

export default function ProjectDetailPage() {
  const params = useParams<{ project_id: string }>();
  const projectId = decodeURIComponent(params.project_id);
  const projectQuery = useProject(projectId);
  const runsQuery = useRuns();
  const gddQuery = useProjectGddDocuments(projectId);

  const runs = useMemo(
    () => (runsQuery.data ?? []).filter((run) => run.project_id === projectId),
    [projectId, runsQuery.data],
  );

  const documents = gddQuery.data ?? [];
  const project = projectQuery.data;

  return (
    <div className="mx-auto w-full max-w-[1440px] p-4 sm:p-6">
      {projectQuery.isError ? (
        <EmptyPanel title="Project unavailable" body={projectQuery.error.message} />
      ) : (
        <>
          <ProjectHeader
            project={project}
            loading={projectQuery.isPending}
            action={
              project ? (
                <DeltaRunDialog
                  projectId={project.id}
                  defaultGddFile={project.source_document}
                />
              ) : null
            }
          />

          {projectQuery.isPending ? (
            <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-24 w-full" />
              ))}
            </div>
          ) : (
            <ProjectMetricGrid
              projects={project ? [project] : []}
              runs={runs}
              documents={documents}
            />
          )}

          <section className="mb-6 rounded-lg border border-border bg-slate-950/30">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                <FileClock className="size-4 text-indigo-300" />
                GDD version history
              </div>
              <span className="text-[12px] text-slate-500">
                {documents.length} versions
              </span>
            </div>
            <div className="p-4">
              <GddVersionHistory
                documents={documents}
                loading={gddQuery.isPending}
              />
            </div>
          </section>

          <section className="rounded-lg border border-border bg-slate-950/30">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                <Workflow className="size-4 text-indigo-300" />
                Run history
              </div>
              <span className="text-[12px] text-slate-500">
                {runs.length} runs
              </span>
            </div>
            <div className="p-4">
              {runsQuery.isPending ? (
                <div className="grid gap-2">
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                </div>
              ) : (
                <ProjectRunTable
                  runs={runs}
                  emptyBody="Trigger a DELTA run to compare the next GDD version."
                />
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
