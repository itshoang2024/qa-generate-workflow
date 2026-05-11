"use client";

import { type ElementType, type ReactNode, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  CalendarClock,
  CheckCircle2,
  FileClock,
  FileText,
  GitBranch,
  Loader2,
  Play,
  Plus,
  Workflow,
} from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCreateProject, useTriggerRun } from "@/lib/mutations";
import type { GDDDocument, Project, Run } from "@/lib/types";
import { cn } from "@/lib/utils";

export const DEFAULT_GDD_FILE = "data/GDD_Sample_Snake_Escape.docx";

const newProjectSchema = z.object({
  name: z.string().trim().min(1, "Project name is required."),
  source_document: z.string().trim().optional(),
  gdd_file: z.string().trim().min(1, "GDD file is required."),
});

const deltaRunSchema = z.object({
  gdd_file: z.string().trim().min(1, "GDD file is required."),
});

type NewProjectValues = z.infer<typeof newProjectSchema>;
type DeltaRunValues = z.infer<typeof deltaRunSchema>;

function cleanOptional(value?: string): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

export function formatDate(iso?: string | null): string {
  if (!iso) return "-";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatBytes(bytes?: number | null): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

export function shortId(value?: string | null, length = 10): string {
  if (!value) return "-";
  return value.length > length ? `${value.slice(0, length)}...` : value;
}

function FieldError({ children }: { children?: ReactNode }) {
  if (!children) return null;
  return <div className="mt-1 text-[12px] text-rose-300">{children}</div>;
}

export function IdChip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex max-w-full items-center truncate rounded bg-slate-500/[0.12] px-1.5 py-0.5 font-mono text-[11.5px] leading-none text-slate-400">
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    COMPLETED: "bg-emerald-500/15 text-emerald-400",
    RUNNING: "bg-sky-500/15 text-sky-300",
    CREATED: "bg-slate-500/15 text-slate-300",
    FAILED: "bg-rose-500/15 text-rose-300",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium whitespace-nowrap",
        map[status] ?? "bg-slate-500/15 text-slate-400",
      )}
    >
      {status === "COMPLETED" ? <CheckCircle2 className="size-3" /> : null}
      {status}
    </span>
  );
}

export function ModeBadge({ mode }: { mode: string }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium whitespace-nowrap",
        mode === "DELTA"
          ? "bg-amber-500/15 text-amber-300"
          : "bg-indigo-500/15 text-indigo-300",
      )}
    >
      {mode}
    </span>
  );
}

export function GddStatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    USER_PROVIDED: "bg-emerald-500/15 text-emerald-400",
    AI_GENERATED: "bg-indigo-500/15 text-indigo-300",
    PENDING: "bg-amber-500/15 text-amber-300",
  };

  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium whitespace-nowrap",
        map[status] ?? "bg-slate-500/15 text-slate-400",
      )}
    >
      {status}
    </span>
  );
}

export function MetricTile({
  icon: Icon,
  label,
  value,
}: {
  icon: ElementType;
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-slate-950/40 p-3">
      <div className="mb-2 flex items-center gap-2 text-[12px] font-medium text-slate-400">
        <Icon className="size-3.5 text-indigo-300" />
        {label}
      </div>
      <div className="text-xl font-semibold text-slate-50">{value}</div>
    </div>
  );
}

export function EmptyPanel({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex min-h-[220px] flex-col items-center justify-center rounded-lg border border-dashed border-slate-700 bg-slate-950/40 px-6 text-center">
      <div className="mb-3 flex size-10 items-center justify-center rounded-lg bg-slate-800 text-slate-300">
        <Workflow className="size-5" />
      </div>
      <div className="text-sm font-semibold text-slate-100">{title}</div>
      <div className="mt-1 max-w-md text-[13px] text-slate-400">{body}</div>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function NewProjectDialog({ ctaLabel = "New project" }: { ctaLabel?: string }) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const createProject = useCreateProject();
  const triggerRun = useTriggerRun();
  const form = useForm<NewProjectValues>({
    resolver: zodResolver(newProjectSchema),
    defaultValues: {
      name: "",
      source_document: "",
      gdd_file: DEFAULT_GDD_FILE,
    },
  });

  const isBusy =
    form.formState.isSubmitting || createProject.isPending || triggerRun.isPending;

  async function triggerNewGame(values: NewProjectValues) {
    const result = await triggerRun.mutateAsync({
      project_name: values.name.trim(),
      gdd_file: values.gdd_file.trim(),
    });
    setOpen(false);
    form.reset({ name: "", source_document: "", gdd_file: DEFAULT_GDD_FILE });
    router.push(`/runs/${result.run_id}`);
  }

  const createRecordOnly = form.handleSubmit(async (values) => {
    const project = await createProject.mutateAsync({
      name: values.name.trim(),
      source_document: cleanOptional(values.source_document) ?? values.gdd_file.trim(),
    });
    setOpen(false);
    form.reset({ name: "", source_document: "", gdd_file: DEFAULT_GDD_FILE });
    router.push(`/projects/${project.id}`);
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button size="sm" />}>
        <Plus className="size-3.5" />
        {ctaLabel}
      </DialogTrigger>
      <DialogContent className="max-w-[560px] bg-slate-950">
        <DialogHeader>
          <DialogTitle>Create project</DialogTitle>
        </DialogHeader>
        <form className="grid gap-4" onSubmit={form.handleSubmit(triggerNewGame)}>
          <label className="grid gap-1.5">
            <span className="text-[12px] font-medium text-slate-300">
              Project name
            </span>
            <Input
              aria-invalid={Boolean(form.formState.errors.name)}
              placeholder="Snake Escape"
              {...form.register("name")}
            />
            <FieldError>{form.formState.errors.name?.message}</FieldError>
          </label>

          <label className="grid gap-1.5">
            <span className="text-[12px] font-medium text-slate-300">
              Source document
            </span>
            <Input
              aria-invalid={Boolean(form.formState.errors.source_document)}
              placeholder={DEFAULT_GDD_FILE}
              {...form.register("source_document")}
            />
            <FieldError>{form.formState.errors.source_document?.message}</FieldError>
          </label>

          <label className="grid gap-1.5">
            <span className="text-[12px] font-medium text-slate-300">
              GDD file
            </span>
            <Input
              aria-invalid={Boolean(form.formState.errors.gdd_file)}
              {...form.register("gdd_file")}
            />
            <FieldError>{form.formState.errors.gdd_file?.message}</FieldError>
          </label>

          <DialogFooter className="mt-1">
            <Button
              type="button"
              variant="outline"
              disabled={isBusy}
              onClick={createRecordOnly}
            >
              {createProject.isPending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <FileText className="size-3.5" />
              )}
              Create record
            </Button>
            <Button type="submit" disabled={isBusy}>
              {triggerRun.isPending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Play className="size-3.5" />
              )}
              Create + trigger
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function DeltaRunDialog({
  projectId,
  defaultGddFile,
}: {
  projectId: string;
  defaultGddFile?: string;
}) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const triggerRun = useTriggerRun();
  const form = useForm<DeltaRunValues>({
    resolver: zodResolver(deltaRunSchema),
    defaultValues: {
      gdd_file: defaultGddFile || DEFAULT_GDD_FILE,
    },
  });

  async function triggerDelta(values: DeltaRunValues) {
    const result = await triggerRun.mutateAsync({
      project_id: projectId,
      gdd_file: values.gdd_file.trim(),
    });
    setOpen(false);
    router.push(`/runs/${result.run_id}`);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button size="sm" />}>
        <GitBranch className="size-3.5" />
        Trigger DELTA
      </DialogTrigger>
      <DialogContent className="max-w-[560px] bg-slate-950">
        <DialogHeader>
          <DialogTitle>Trigger DELTA run</DialogTitle>
        </DialogHeader>
        <form className="grid gap-4" onSubmit={form.handleSubmit(triggerDelta)}>
          <label className="grid gap-1.5">
            <span className="text-[12px] font-medium text-slate-300">
              GDD file
            </span>
            <Input
              aria-invalid={Boolean(form.formState.errors.gdd_file)}
              {...form.register("gdd_file")}
            />
            <FieldError>{form.formState.errors.gdd_file?.message}</FieldError>
          </label>
          <DialogFooter className="mt-1">
            <Button type="submit" disabled={triggerRun.isPending}>
              {triggerRun.isPending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Play className="size-3.5" />
              )}
              Trigger run
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ProjectRunTable({
  runs,
  emptyTitle = "No runs yet",
  emptyBody = "Trigger a run to populate the workflow timeline.",
}: {
  runs: Run[];
  emptyTitle?: string;
  emptyBody?: string;
}) {
  if (runs.length === 0) {
    return <EmptyPanel title={emptyTitle} body={emptyBody} />;
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <Table>
        <TableHeader>
          <TableRow className="bg-slate-900/60 hover:bg-slate-900/60">
            <TableHead>Run</TableHead>
            <TableHead>Mode</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Stage</TableHead>
            <TableHead>Artifacts</TableHead>
            <TableHead>Updated</TableHead>
            <TableHead className="text-right">Open</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.map((run) => (
            <TableRow key={run.id}>
              <TableCell>
                <IdChip>{run.id}</IdChip>
              </TableCell>
              <TableCell>
                <ModeBadge mode={run.mode} />
              </TableCell>
              <TableCell>
                <StatusBadge status={run.status} />
              </TableCell>
              <TableCell className="font-mono text-[11.5px] text-slate-400">
                {run.current_stage}
              </TableCell>
              <TableCell className="text-slate-300">
                {(run.coverage_report.feature_count ?? 0).toString()}F /{" "}
                {(run.coverage_report.task_count ?? 0).toString()}T /{" "}
                {(run.coverage_report.test_case_count ?? 0).toString()}TC
              </TableCell>
              <TableCell className="text-slate-400">
                {formatDate(run.updated_at)}
              </TableCell>
              <TableCell className="text-right">
                <Link
                  href={`/runs/${run.id}`}
                  className={cn(
                    buttonVariants({ variant: "ghost", size: "sm" }),
                    "text-slate-200",
                  )}
                >
                  View
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function GddVersionHistory({
  documents,
  loading,
}: {
  documents?: GDDDocument[];
  loading: boolean;
}) {
  const ordered = useMemo(
    () =>
      [...(documents ?? [])].sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      ),
    [documents],
  );

  if (loading) {
    return (
      <div className="grid gap-2">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  if (ordered.length === 0) {
    return (
      <EmptyPanel
        title="No GDD versions"
        body="Registered GDD documents will appear after context loading."
      />
    );
  }

  return (
    <div className="grid gap-2">
      {ordered.map((doc) => (
        <div
          key={doc.id}
          className="grid gap-3 rounded-lg border border-border bg-slate-950/40 p-3 md:grid-cols-[160px_1fr_auto]"
        >
          <div className="min-w-0">
            <div className="mb-1 flex items-center gap-2">
              <FileClock className="size-3.5 text-indigo-300" />
              <span className="font-mono text-sm font-semibold text-slate-100">
                {doc.version_id}
              </span>
            </div>
            <GddStatusBadge status={doc.description_status} />
          </div>

          <div className="min-w-0 text-[13px] text-slate-300">
            <div className="truncate font-medium text-slate-100">
              {doc.file_name}
            </div>
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[12px] text-slate-400">
              <span>{formatBytes(doc.size_bytes)}</span>
              <span>sha {shortId(doc.sha256, 12)}</span>
              <span>origin {doc.origin}</span>
              <span>parent {shortId(doc.parent_document_id, 12)}</span>
            </div>
          </div>

          <div className="flex items-start justify-start text-[12px] text-slate-400 md:justify-end">
            {formatDate(doc.created_at)}
          </div>
        </div>
      ))}
    </div>
  );
}

export function ProjectHeader({
  project,
  loading,
  action,
}: {
  project?: Project;
  loading?: boolean;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
      <div className="min-w-0">
        <div className="mb-2 flex items-center gap-2 text-[12px] font-medium uppercase text-slate-500">
          <FileText className="size-3.5" />
          Project
        </div>
        <h1 className="truncate text-2xl font-semibold tracking-normal text-slate-50">
          {loading ? <Skeleton className="inline-block h-7 w-56" /> : project?.name}
        </h1>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[13px] text-slate-400">
          {project?.id ? <IdChip>{project.id}</IdChip> : null}
          {project?.created_at ? <span>{formatDate(project.created_at)}</span> : null}
          {project?.source_document ? (
            <span className="max-w-full truncate font-mono">
              {project.source_document}
            </span>
          ) : null}
        </div>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export function ProjectMetricGrid({
  projects,
  runs,
  documents,
}: {
  projects?: Project[];
  runs?: Run[];
  documents?: GDDDocument[];
}) {
  const latestRun = runs?.[0];

  return (
    <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <MetricTile icon={FileText} label="Projects" value={projects?.length ?? 0} />
      <MetricTile icon={Workflow} label="Runs" value={runs?.length ?? 0} />
      <MetricTile
        icon={CalendarClock}
        label="Latest run"
        value={latestRun ? formatDate(latestRun.updated_at) : "-"}
      />
      <MetricTile icon={FileClock} label="GDD versions" value={documents?.length ?? 0} />
    </div>
  );
}
