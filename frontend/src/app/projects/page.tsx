"use client";

import { useMemo } from "react";
import Link from "next/link";
import { ArrowUpRight, FileText, Workflow } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useProjects, useRuns } from "@/lib/queries";
import type { Project, Run } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  EmptyPanel,
  formatDate,
  IdChip,
  ModeBadge,
  NewProjectDialog,
  ProjectMetricGrid,
  StatusBadge,
} from "./_components";

function ProjectRow({
  project,
  runs,
}: {
  project: Project;
  runs: Run[];
}) {
  const latestRun = runs[0];

  return (
    <div className="grid gap-3 border-b border-border px-4 py-3 last:border-b-0 md:grid-cols-[minmax(0,1.4fr)_140px_180px_88px] md:items-center">
      <div className="min-w-0">
        <Link
          href={`/projects/${project.id}`}
          className="group inline-flex max-w-full items-center gap-1.5 text-sm font-semibold text-slate-100 hover:text-indigo-300"
        >
          <span className="truncate">{project.name}</span>
          <ArrowUpRight className="size-3.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-[12px] text-slate-400">
          <IdChip>{project.id}</IdChip>
          {project.source_document ? (
            <span className="max-w-full truncate font-mono">
              {project.source_document}
            </span>
          ) : null}
        </div>
      </div>

      <div className="text-[13px] text-slate-300">
        <span className="font-semibold text-slate-100">{runs.length}</span> runs
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {latestRun ? (
          <>
            <ModeBadge mode={latestRun.mode} />
            <StatusBadge status={latestRun.status} />
          </>
        ) : (
          <span className="text-[13px] text-slate-500">No runs</span>
        )}
      </div>

      <div className="text-left text-[12px] text-slate-400 md:text-right">
        {latestRun ? formatDate(latestRun.updated_at) : formatDate(project.created_at)}
      </div>
    </div>
  );
}

function ProjectListSkeleton() {
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      {Array.from({ length: 4 }).map((_, index) => (
        <div
          key={index}
          className="grid gap-3 border-b border-border px-4 py-3 last:border-b-0 md:grid-cols-[minmax(0,1.4fr)_140px_180px_88px]"
        >
          <div>
            <Skeleton className="h-4 w-44" />
            <Skeleton className="mt-2 h-3 w-72 max-w-full" />
          </div>
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-5 w-36" />
          <Skeleton className="h-4 w-20 md:ml-auto" />
        </div>
      ))}
    </div>
  );
}

export default function ProjectsPage() {
  const projectsQuery = useProjects();
  const runsQuery = useRuns();
  const projects = projectsQuery.data ?? [];
  const runs = useMemo(() => runsQuery.data ?? [], [runsQuery.data]);

  const runsByProject = useMemo(() => {
    const map = new Map<string, Run[]>();
    for (const run of runs) {
      const bucket = map.get(run.project_id) ?? [];
      bucket.push(run);
      map.set(run.project_id, bucket);
    }
    return map;
  }, [runs]);

  return (
    <div className="mx-auto w-full max-w-[1440px] p-4 sm:p-6">
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="mb-2 flex items-center gap-2 text-[12px] font-medium uppercase text-slate-500">
            <FileText className="size-3.5" />
            Workspace
          </div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-50">
            Projects
          </h1>
          <div className="mt-2 max-w-2xl text-[13px] text-slate-400">
            Game QA workflow projects and their latest run state.
          </div>
        </div>
        <NewProjectDialog />
      </div>

      <ProjectMetricGrid projects={projects} runs={runs} />

      <section className="rounded-lg border border-border bg-slate-950/30">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
            <Workflow className="size-4 text-indigo-300" />
            Project list
          </div>
          <span className="text-[12px] text-slate-500">
            {projects.length} total
          </span>
        </div>

        {projectsQuery.isPending ? (
          <ProjectListSkeleton />
        ) : projectsQuery.isError ? (
          <div className="p-4">
            <EmptyPanel
              title="Projects unavailable"
              body={projectsQuery.error.message}
            />
          </div>
        ) : projects.length === 0 ? (
          <div className="p-4">
            <EmptyPanel
              title="No projects yet"
              body="Create the first project to start a NEW_GAME run."
              action={<NewProjectDialog ctaLabel="Create your first project" />}
            />
          </div>
        ) : (
          <div>
            <div className="hidden grid-cols-[minmax(0,1.4fr)_140px_180px_88px] border-b border-border bg-slate-900/60 px-4 py-2 text-[11px] font-medium uppercase text-slate-500 md:grid">
              <span>Project</span>
              <span>Runs</span>
              <span>Latest</span>
              <span className="text-right">Updated</span>
            </div>
            {projects.map((project) => (
              <ProjectRow
                key={project.id}
                project={project}
                runs={runsByProject.get(project.id) ?? []}
              />
            ))}
          </div>
        )}
      </section>

      <div className="mt-4 flex justify-end">
        <Link
          href="/runs"
          className={cn(
            buttonVariants({ variant: "ghost", size: "sm" }),
            "text-slate-300",
          )}
        >
          View all runs
        </Link>
      </div>
    </div>
  );
}
