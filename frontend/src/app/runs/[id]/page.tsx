"use client";

import { useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ChevronRight,
  RefreshCw,
  BadgeCheck,
  Workflow,
  Play,
  FileText,
  ShieldAlert,
  ListChecks,
  Database,
  AlertTriangle,
  Inbox,
  ChevronDown,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  useRun,
  useTimeline,
  useCoverage,
  useAgentRuns,
  useFeatures,
  useEpics,
  useStories,
  useTasks,
  useTestCases,
  useValidationIssues,
  useHil0Questions,
  useReviewQueue,
  queryKeys,
} from "@/lib/queries";
import { ApiError } from "@/lib/api";
import {
  useCreateReviewDecision,
  useFinalizeRun,
  useLoadContext,
  useResolveHil0Question,
  useResolveHil0Questions,
  useRunAgentA,
  useRunAgentB,
  useRunAgentC,
  useSignOffRun,
} from "@/lib/mutations";
import type {
  AgentRun,
  CoverageReport,
  Epic,
  Feature,
  HilTier,
  HIL0Question,
  QATask,
  ReviewQueue,
  ReviewQueueItem,
  Run,
  StageEvent,
  Story,
  TestCase,
  ValidationIssue,
} from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// ─── Local supplemental types ────────────────────────────────────────────────

// CoverageReport.gdd_version_metadata.source_metadata is Record<string,unknown>
// in the shared types file; we narrow it here for the UI.
type GddSourceMeta = { file_name: string; sha256: string; size_bytes: number };

// AgentRun.output_snapshot is Record<string,unknown> in shared types; we use
// this narrowed shape to access known fields without casting at every site.
type AgentOutput = {
  attempts?: Array<{
    attempt: number;
    outcome: string;
    issue_codes: string[];
    target_section_ids: string[];
  }>;
  attempt_count?: number;
  retry_exhausted?: boolean;
  coverage_report?: {
    covered_sections: string[];
    uncovered_sections: string[];
    total_input_sections: number;
  };
  feature_count?: number;
  epic_count?: number;
  task_count?: number;
  story_count?: number;
  [key: string]: unknown;
};

// ─── Utilities ───────────────────────────────────────────────────────────────

function normalizeCoverageReport(
  report?: Partial<CoverageReport> | null,
): CoverageReport {
  return {
    total_sections: report?.total_sections ?? 0,
    actionable_sections: report?.actionable_sections ?? 0,
    covered_sections: report?.covered_sections ?? [],
    uncovered_sections: report?.uncovered_sections ?? [],
    feature_count: report?.feature_count ?? 0,
    task_count: report?.task_count ?? 0,
    test_case_count: report?.test_case_count ?? 0,
    validation_issue_count: report?.validation_issue_count ?? 0,
    tasks_by_assignee: report?.tasks_by_assignee ?? {},
    tasks_by_priority: report?.tasks_by_priority ?? {},
    risk_summary: {
      total: report?.risk_summary?.total ?? 0,
      by_severity: report?.risk_summary?.by_severity ?? {},
      by_code: report?.risk_summary?.by_code ?? {},
    },
    sync_summary: {
      total: report?.sync_summary?.total ?? 0,
      by_status: report?.sync_summary?.by_status ?? {},
      by_phase: report?.sync_summary?.by_phase ?? {},
    },
    gdd_version_metadata: {
      gdd_document_id: report?.gdd_version_metadata?.gdd_document_id ?? null,
      source_version_id: report?.gdd_version_metadata?.source_version_id ?? null,
      source_metadata: report?.gdd_version_metadata?.source_metadata ?? {},
    },
    sign_off: {
      signed_off: report?.sign_off?.signed_off ?? false,
      signed_off_by: report?.sign_off?.signed_off_by ?? null,
      signed_off_at: report?.sign_off?.signed_off_at ?? null,
    },
  };
}

function fmtTime(iso: string | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toISOString().slice(11, 19);
}

// ─── Primitive components ─────────────────────────────────────────────────────

function IdChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-mono text-[11.5px] leading-none px-1.5 py-0.5 rounded bg-slate-500/[0.12] text-slate-400 whitespace-nowrap">
      {children}
    </span>
  );
}

function InlineSkeleton({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-block animate-pulse rounded-md bg-muted", className)}
    />
  );
}

function LaneBadge({ lane }: { lane: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium whitespace-nowrap",
        lane === "AUTO" && "bg-emerald-500/15 text-emerald-400",
        lane === "BATCH" && "bg-amber-500/15 text-amber-400",
        lane === "BLOCK" && "bg-rose-500/15 text-rose-400",
        !["AUTO", "BATCH", "BLOCK"].includes(lane) && "bg-slate-500/15 text-slate-400",
      )}
    >
      {lane}
    </span>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const level = severity.startsWith("S1") ? "S1" : severity.startsWith("S2") ? "S2" : "S3";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
        level === "S1" && "bg-rose-500/15 text-rose-300",
        level === "S2" && "bg-amber-500/15 text-amber-300",
        level === "S3" && "bg-slate-500/15 text-slate-300",
      )}
    >
      {level}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    ok: "bg-emerald-500/15 text-emerald-400",
    warn: "bg-amber-500/15 text-amber-400",
    fail: "bg-rose-500/15 text-rose-400",
    COMPLETED: "bg-emerald-500/15 text-emerald-400",
    RUNNING: "bg-indigo-500/15 text-indigo-400",
    FAILED: "bg-rose-500/15 text-rose-400",
    PENDING: "bg-slate-500/15 text-slate-400",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
        map[status] ?? "bg-slate-500/15 text-slate-400",
      )}
    >
      {status === "COMPLETED" && (
        <span className="size-1.5 rounded-full bg-current" />
      )}
      {status}
    </span>
  );
}

function AttemptOutcomeBadge({ outcome }: { outcome: string }) {
  const map: Record<string, string> = {
    validation_retry: "bg-amber-500/15 text-amber-400",
    success: "bg-emerald-500/15 text-emerald-400",
    failed: "bg-rose-500/15 text-rose-400",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
        map[outcome] ?? "bg-slate-500/15 text-slate-400",
      )}
    >
      {outcome}
    </span>
  );
}

function SectionLabel({
  children,
  right,
}: {
  children: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-2.5">
      <span className="text-[10.5px] font-medium uppercase tracking-[0.06em] text-slate-500">
        {children}
      </span>
      {right}
    </div>
  );
}

function ConfBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const barColor =
    value >= 0.9
      ? "bg-emerald-500"
      : value >= 0.8
        ? "bg-amber-500"
        : "bg-rose-500";
  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 h-1 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full", barColor)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="font-mono text-[11px] text-slate-400 w-7 text-right">
        {value.toFixed(2)}
      </span>
    </div>
  );
}

function AssigneeCell({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("");
  return (
    <div className="flex items-center gap-2">
      <div className="size-5 rounded-full bg-slate-700 flex items-center justify-center text-[9.5px] font-semibold text-slate-100 shrink-0">
        {initials}
      </div>
      <span className="text-[13px] text-slate-200">{name}</span>
    </div>
  );
}

function SrcChips({ src }: { src: string[] }) {
  return (
    <div className="flex flex-wrap gap-1">
      {src.map((s, i) => (
        <IdChip key={i}>{s}</IdChip>
      ))}
    </div>
  );
}

// ─── Timeline icons per stage ─────────────────────────────────────────────────

const STAGE_ICONS: Record<string, React.ElementType> = {
  S0_TRIGGER: Play,
  S1_CONTEXT_LOADER: FileText,
  S2_AGENT_A: Workflow,
  S3_VALIDATION_A: ShieldAlert,
  "HIL-1": ListChecks,
  "HIL-2": ListChecks,
  "HIL-3": ListChecks,
  "SYNC-A": Database,
  "SYNC-B": Database,
  "SYNC-C": Database,
  S4_AGENT_B: Workflow,
  S5_VALIDATION_B_SYNC: ShieldAlert,
  S6_AGENT_C: Workflow,
  S7_VALIDATION_C_SYNC: ShieldAlert,
  FINAL_COVERAGE: BadgeCheck,
};

// ─── AgentRunsPanel ───────────────────────────────────────────────────────────

function AgentRunRow({
  row,
  expanded,
  onToggle,
}: {
  row: AgentRun;
  expanded: boolean;
  onToggle: () => void;
}) {
  const out = row.output_snapshot as AgentOutput;
  const inp = row.input_snapshot as Record<string, unknown>;
  const attempts = out.attempts ?? [];
  const exhausted = !!out.retry_exhausted;
  const attemptCount = out.attempt_count as number | undefined;
  const hasAttempts = attempts.length > 0;

  return (
    <div className="border-t border-border">
      <button
        onClick={hasAttempts ? onToggle : undefined}
        disabled={!hasAttempts}
        className={cn(
          "w-full text-left px-3.5 py-3 grid gap-3.5 items-center",
          "text-slate-300 bg-transparent",
          hasAttempts && "hover:bg-slate-800/40 cursor-pointer",
          !hasAttempts && "cursor-default",
        )}
        style={{ gridTemplateColumns: "20px 220px 1fr 90px 110px 90px" }}
      >
        <ChevronDown
          size={14}
          className={cn(
            "text-slate-500 shrink-0 transition-transform",
            !expanded && "-rotate-90",
            !hasAttempts && "opacity-0",
          )}
        />
        <div className="flex flex-col gap-1">
          <span className="text-[13.5px] font-semibold text-slate-100">
            {row.agent_name}
          </span>
          <div className="flex gap-1.5 items-center">
            <IdChip>{row.stage}</IdChip>
            <span className="font-mono text-[11px] text-slate-500">
              {row.provider}
            </span>
          </div>
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {(["feature_count", "epic_count", "task_count", "story_count"] as const).map(
            (k) =>
              out[k] != null ? (
                <span
                  key={k}
                  className="font-mono text-[11px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300"
                >
                  {out[k] as number} {k.replace("_count", "")}
                </span>
              ) : null,
          )}
          {(inp.section_count as number | undefined) != null && (
            <span className="font-mono text-[11px] px-2 py-0.5 rounded-full bg-slate-500/12 text-slate-400">
              {inp.section_count as number} sections in
            </span>
          )}
        </div>
        <div className="font-mono text-[12.5px]">
          {attemptCount != null ? (
            <>
              <span className="font-semibold text-slate-100">{attemptCount}</span>
              <span className="text-slate-500"> attempts</span>
            </>
          ) : (
            <span className="text-slate-500">—</span>
          )}
        </div>
        <div>
          {exhausted ? (
            <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium bg-rose-500/15 text-rose-400">
              retry exhausted
            </span>
          ) : (attemptCount ?? 0) > 1 ? (
            <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium bg-amber-500/15 text-amber-400">
              retried
            </span>
          ) : (
            <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium bg-emerald-500/15 text-emerald-400">
              clean
            </span>
          )}
        </div>
        <div className="font-mono text-[11px] text-slate-500 text-right">
          {fmtTime(row.created_at)}
        </div>
      </button>

      {expanded && hasAttempts && (
        <div className="px-3.5 pb-3.5 pl-12 bg-slate-950/35">
          <div className="text-[11px] font-medium uppercase tracking-[0.06em] text-slate-500 py-2.5">
            Attempts log
          </div>
          <div className="border border-border rounded-lg overflow-hidden">
            {attempts.map((a, i) => (
              <div
                key={i}
                className={cn(
                  "grid gap-3 px-3 py-2.5 items-center text-[12.5px]",
                  i > 0 && "border-t border-border",
                )}
                style={{ gridTemplateColumns: "60px 1fr 200px 1fr" }}
              >
                <span className="font-mono text-slate-400">#{a.attempt}</span>
                <AttemptOutcomeBadge outcome={a.outcome} />
                <div className="flex flex-wrap gap-1">
                  {(a.issue_codes ?? []).map((c, j) => (
                    <span
                      key={j}
                      className="font-mono text-[11px] px-2 py-0.5 rounded-full bg-rose-500/12 text-rose-400"
                    >
                      {c}
                    </span>
                  ))}
                </div>
                <div className="flex flex-wrap gap-1 justify-end">
                  {(a.target_section_ids ?? []).length === 0 ? (
                    <span className="font-mono text-[11px] text-slate-500">
                      no targets
                    </span>
                  ) : (
                    (a.target_section_ids ?? []).map((s, j) => (
                      <IdChip key={j}>{s}</IdChip>
                    ))
                  )}
                </div>
              </div>
            ))}
          </div>

          {out.coverage_report && (
            <div className="mt-3 grid grid-cols-3 gap-2.5 text-[12px]">
              {(
                [
                  ["Total input", out.coverage_report.total_input_sections, "text-slate-100"],
                  ["Covered", (out.coverage_report.covered_sections ?? []).length, "text-emerald-400"],
                  [
                    "Uncovered",
                    (out.coverage_report.uncovered_sections ?? []).join(", ") || "—",
                    "text-rose-400",
                  ],
                ] as const
              ).map(([label, value, color]) => (
                <div
                  key={label}
                  className="px-2.5 py-2 bg-card rounded-lg border border-border"
                >
                  <div className="text-[11px] text-slate-500">{label}</div>
                  <div className={cn("font-mono text-sm font-semibold mt-0.5", color)}>
                    {value}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AgentRunsPanel({ runId }: { runId: string }) {
  const { data, isPending, isError } = useAgentRuns(runId);
  const runs = (data ?? []) as AgentRun[];
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const anyRetryExhausted = runs.some((r) => (r.output_snapshot as AgentOutput)?.retry_exhausted);

  // Auto-expand the first agent with retry_exhausted on initial load
  if (!isPending && runs.length > 0 && expandedId === null) {
    const flagged = runs.find((r) => (r.output_snapshot as AgentOutput)?.retry_exhausted);
    if (flagged) {
      setExpandedId(flagged.id);
    }
  }

  if (isPending) {
    return (
      <div className="rounded-xl ring-1 ring-foreground/10 bg-card overflow-hidden">
        <div className="p-3.5 space-y-2">
          <Skeleton className="h-3.5 w-44" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-xl ring-1 ring-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-400">
        Failed to load agent runs.
      </div>
    );
  }

  return (
    <div className="rounded-xl ring-1 ring-foreground/10 bg-card overflow-hidden">
      <div className="flex items-center justify-between px-3.5 py-3">
        <div className="flex items-center gap-2.5">
          <div className="size-7 rounded-lg bg-indigo-500/14 text-indigo-300 flex items-center justify-center shrink-0">
            <Workflow size={14} />
          </div>
          <div className="flex flex-col">
            <span className="text-[13.5px] font-semibold text-slate-100">
              Agent runs
            </span>
            <span className="text-[11.5px] text-slate-400">
              {runs.length} executions ·{" "}
              {anyRetryExhausted ? (
                <span className="text-rose-400">1 retry exhausted</span>
              ) : (
                "no failed retries"
              )}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <button className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-lg text-[12.5px] font-medium text-slate-400 hover:bg-slate-800 hover:text-slate-100 transition-colors">
            <RefreshCw size={13} />
            Replay
          </button>
          <button className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-lg text-[12.5px] font-medium text-slate-300 border border-slate-700 hover:bg-slate-800 transition-colors">
            <FileText size={13} />
            Open logs
          </button>
        </div>
      </div>

      <div
        className="grid gap-3.5 px-3.5 py-2 text-[10.5px] font-medium uppercase tracking-[0.06em] text-slate-500 border-t border-border bg-slate-950/25"
        style={{ gridTemplateColumns: "20px 220px 1fr 90px 110px 90px" }}
      >
        <span />
        <span>Agent · stage</span>
        <span>Outputs</span>
        <span>Attempts</span>
        <span>Status</span>
        <span className="text-right">Time</span>
      </div>

      {runs.map((r) => (
        <AgentRunRow
          key={r.id}
          row={r}
          expanded={expandedId === r.id}
          onToggle={() => setExpandedId(expandedId === r.id ? null : r.id)}
        />
      ))}
    </div>
  );
}

// ─── TimelinePanel ────────────────────────────────────────────────────────────

function TimelineStage({
  event,
  isFirst,
  isLast,
}: {
  event: StageEvent;
  isFirst: boolean;
  isLast: boolean;
}) {
  const Icon = STAGE_ICONS[event.stage] ?? Play;
  const dotColor =
    event.status === "warn"
      ? { ring: "bg-amber-500", glow: "bg-amber-500/15", text: "text-amber-400", border: "border-l-amber-500" }
      : event.status === "fail"
        ? { ring: "bg-rose-500", glow: "bg-rose-500/15", text: "text-rose-400", border: "border-l-rose-500" }
        : { ring: "bg-emerald-500", glow: "bg-emerald-500/15", text: "text-emerald-400", border: "border-l-emerald-500" };

  return (
    <div className="flex gap-3.5 relative">
      <div className="w-7 shrink-0 flex flex-col items-center relative">
        <span
          className="absolute top-0 w-px bg-border"
          style={{ bottom: "50%", background: isFirst ? "transparent" : undefined }}
        />
        <span
          className="absolute w-px bg-border"
          style={{ top: "50%", bottom: 0, background: isLast ? "transparent" : undefined }}
        />
        <div
          className={cn(
            "relative z-10 mt-3.5 size-7 rounded-full flex items-center justify-center ring-4 ring-background",
            dotColor.glow,
            dotColor.text,
          )}
        >
          <Icon size={14} />
        </div>
      </div>

      <div className="flex-1 pb-3.5">
        <div
          className={cn(
            "rounded-xl ring-1 ring-foreground/10 bg-card p-3 border-l-2",
            dotColor.border,
          )}
        >
          <div className="flex items-center justify-between gap-2.5 mb-1">
            <div className="flex items-center gap-2">
              <IdChip>{event.stage}</IdChip>
              <StatusBadge status={event.status} />
            </div>
            <span className="font-mono text-[11.5px] text-slate-500 whitespace-nowrap">
              {fmtTime(event.created_at)}
            </span>
          </div>
          <p className="text-[13px] text-slate-300 leading-snug">{event.message}</p>
        </div>
      </div>
    </div>
  );
}

function TimelinePanel({ runId }: { runId: string }) {
  const { data, isPending, isError } = useTimeline(runId);
  const events = (data ?? []) as StageEvent[];

  if (isPending) {
    return (
      <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
        <SectionLabel>Pipeline timeline</SectionLabel>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="flex gap-3.5 mb-3.5">
            <Skeleton className="size-7 rounded-full shrink-0" />
            <div className="flex-1 space-y-1.5">
              <Skeleton className="h-3 w-2/5" />
              <Skeleton className="h-2.5 w-3/4" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-xl ring-1 ring-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-400">
        Failed to load timeline.
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-8">
        <div className="flex flex-col items-center gap-3 py-6 text-center">
          <div className="size-10 rounded-full bg-slate-500/14 text-slate-400 flex items-center justify-center">
            <Inbox size={20} />
          </div>
          <p className="text-[15px] font-semibold text-slate-100">
            Run hasn&apos;t started yet
          </p>
          <p className="text-[13px] text-slate-400 max-w-[280px]">
            Trigger a NEW_GAME or DELTA run to populate the pipeline timeline.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <SectionLabel
        right={
          <span className="font-mono text-[11.5px] text-slate-500">
            {events.length} events
          </span>
        }
      >
        Pipeline timeline
      </SectionLabel>
      <div>
        {events.map((e, i) => (
          <TimelineStage
            key={i}
            event={e}
            isFirst={i === 0}
            isLast={i === events.length - 1}
          />
        ))}
      </div>
    </div>
  );
}

// ─── CoveragePanel ────────────────────────────────────────────────────────────

function CoverageBar({ covered, total }: { covered: number; total: number }) {
  const pct = total > 0 ? Math.round((covered / total) * 100) : 0;
  return (
    <div>
      <div className="flex justify-between items-baseline mb-2">
        <div className="flex items-baseline gap-1.5">
          <span className="font-mono text-[28px] font-semibold tracking-tight text-slate-100">
            {pct}%
          </span>
          <span className="text-[12px] text-slate-400">actionable coverage</span>
        </div>
        <span className="font-mono text-[12px] text-slate-400">
          {covered}/{total}
        </span>
      </div>
      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-indigo-500 to-indigo-400 rounded-full"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function MiniStat({
  label,
  value,
  sub,
  valueClass,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  valueClass?: string;
}) {
  return (
    <div className="flex-1 min-w-0 px-3 py-2.5 bg-slate-950/35 rounded-lg border border-border">
      <div className="text-[10.5px] font-medium uppercase tracking-[0.06em] text-slate-500">
        {label}
      </div>
      <div
        className={cn(
          "font-mono text-[22px] font-semibold tracking-tight mt-0.5",
          valueClass ?? "text-slate-100",
        )}
      >
        {value}
      </div>
      {sub && (
        <div className="text-[11.5px] text-slate-400 mt-0.5">{sub}</div>
      )}
    </div>
  );
}

function CoveragePanel({ runId }: { runId: string }) {
  const { data, isPending, isError } = useCoverage(runId);

  if (isPending) {
    return (
      <div className="flex flex-col gap-3.5">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="rounded-xl ring-1 ring-foreground/10 bg-card p-4 space-y-2.5">
            <Skeleton className="h-3 w-28" />
            <Skeleton className="h-7 w-3/5" />
            <Skeleton className="h-2.5 w-full" />
          </div>
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-xl ring-1 ring-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-400">
        Failed to load coverage data.
      </div>
    );
  }

  const c = normalizeCoverageReport(data);
  const uncovered = c.uncovered_sections ?? [];
  const coveredCount = Math.max(0, c.actionable_sections - uncovered.length);
  const nonActionableCount = Math.max(0, c.total_sections - c.actionable_sections);

  return (
    <div className="flex flex-col gap-3.5">
      {/* Coverage bar */}
      <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
        <SectionLabel
          right={
            c.actionable_sections === 0 ? (
              <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium bg-slate-500/15 text-slate-300">
                pending
              </span>
            ) : uncovered.length === 0 ? (
              <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium bg-emerald-500/15 text-emerald-400">
                complete
              </span>
            ) : (
              <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium bg-amber-500/15 text-amber-400">
                {uncovered.length} uncovered
              </span>
            )
          }
        >
          Coverage
        </SectionLabel>
        <CoverageBar covered={coveredCount} total={c.actionable_sections} />
        <div className="mt-3.5 grid grid-cols-2 gap-2">
          <MiniStat
            label="Total sections"
            value={c.total_sections}
            sub="parsed from GDD"
          />
          <MiniStat
            label="Actionable"
            value={c.actionable_sections}
            sub={`${nonActionableCount} non-actionable`}
          />
        </div>
        {uncovered.length > 0 && (
          <div className="mt-3 px-2.5 py-2 rounded-lg bg-rose-500/8 border border-rose-500/25 flex items-center flex-wrap gap-2">
            <AlertTriangle size={13} className="text-rose-400 shrink-0" />
            <span className="text-[12px] text-slate-300">Uncovered:</span>
            {uncovered.map((s, i) => (
              <IdChip key={i}>{s}</IdChip>
            ))}
          </div>
        )}
      </div>

      {/* Artifact totals */}
      <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
        <SectionLabel>Generated artifacts</SectionLabel>
        <div className="grid grid-cols-3 gap-2">
          <MiniStat label="Features" value={c.feature_count} />
          <MiniStat label="Tasks" value={c.task_count} />
          <MiniStat label="Test cases" value={c.test_case_count} />
        </div>
      </div>

      {/* Risk + Sync side by side */}
      <div className="grid grid-cols-2 gap-3.5">
        <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
          <SectionLabel
            right={
              <span className="font-mono text-[11.5px] text-slate-500">
                {c.risk_summary.total} total
              </span>
            }
          >
            Risk · by severity
          </SectionLabel>
          {(["S1", "S2", "S3"] as const).map((sev) => (
            <div
              key={sev}
              className="flex items-center justify-between py-2 border-t border-border"
            >
              <div className="flex items-center gap-2">
                <SeverityBadge severity={sev} />
                <span className="text-[12.5px] text-slate-300">
                  {sev === "S1" ? "Critical" : sev === "S2" ? "Warn" : "Info"}
                </span>
              </div>
              <span className="font-mono text-[13px] text-slate-100">
                {c.risk_summary.by_severity[sev] ?? 0}
              </span>
            </div>
          ))}
          {Object.keys(c.risk_summary.by_code ?? {}).length > 0 && (
            <div className="mt-2.5 pt-2.5 border-t border-border">
              <div className="text-[10.5px] font-medium uppercase tracking-[0.06em] text-slate-500 mb-1.5">
                By code
              </div>
              {Object.entries(c.risk_summary.by_code).map(([code, n]) => (
                <div
                  key={code}
                  className="flex justify-between items-center py-1"
                >
                  <span className="font-mono text-[11px] text-slate-300">
                    {code}
                  </span>
                  <span className="font-mono text-[11px] text-slate-100">
                    {n}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
          <SectionLabel
            right={
              <span className="font-mono text-[11.5px] text-slate-500">
                {c.sync_summary.total} events
              </span>
            }
          >
            Sync · by phase
          </SectionLabel>
          {Object.entries(c.sync_summary.by_phase).map(([phase, count]) => {
            const pct =
              c.sync_summary.total > 0
                ? (count / c.sync_summary.total) * 100
                : 0;
            return (
              <div key={phase} className="mb-2">
                <div className="flex justify-between items-center mb-1">
                  <span className="font-mono text-[11px] font-medium px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-300">
                    {phase}
                  </span>
                  <span className="font-mono text-[12px] text-slate-400">
                    {count}
                  </span>
                </div>
                <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-violet-500 rounded-full"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
          <div className="mt-2.5 pt-2.5 border-t border-border flex items-center justify-between text-[11.5px]">
            <span className="text-slate-400">SUCCESS</span>
            <span className="font-mono text-emerald-400">
              {c.sync_summary.by_status?.SUCCESS ?? 0}/{c.sync_summary.total}
            </span>
          </div>
        </div>
      </div>

      {/* GDD source */}
      <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
        <SectionLabel>GDD source</SectionLabel>
        {(() => {
          const meta = c.gdd_version_metadata.source_metadata as Partial<GddSourceMeta>;
          const hasSource =
            Boolean(c.gdd_version_metadata.gdd_document_id) ||
            Boolean(c.gdd_version_metadata.source_version_id) ||
            Boolean(meta.file_name);
          const sha256 = meta.sha256;

          if (!hasSource) {
            return (
              <div className="flex items-start gap-2.5">
                <div className="size-9 rounded-lg bg-slate-500/15 text-slate-400 flex items-center justify-center shrink-0">
                  <FileText size={16} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-medium text-slate-100">
                    No GDD version loaded
                  </p>
                  <p className="mt-1 text-[12px] text-slate-400">
                    Waiting for S1 context.
                  </p>
                </div>
              </div>
            );
          }
          return (
            <div className="flex items-start gap-2.5">
              <div className="size-9 rounded-lg bg-slate-500/15 text-slate-400 flex items-center justify-center shrink-0">
                <FileText size={16} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-medium text-slate-100 truncate">
                  {meta.file_name ?? "Unknown file"}
                </p>
                <div className="flex flex-wrap gap-1.5 mt-1 items-center">
                  {c.gdd_version_metadata.gdd_document_id ? (
                    <IdChip>{c.gdd_version_metadata.gdd_document_id}</IdChip>
                  ) : null}
                  {c.gdd_version_metadata.source_version_id ? (
                    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium bg-indigo-500/18 text-indigo-300">
                      {c.gdd_version_metadata.source_version_id}
                    </span>
                  ) : null}
                  {typeof meta.size_bytes === "number" ? (
                    <span className="font-mono text-[11px] text-slate-500">
                      {Math.round(meta.size_bytes / 1024)} KB
                    </span>
                  ) : null}
                </div>
                {sha256 ? (
                  <p
                    className="mt-1.5 font-mono text-[11px] text-slate-500 truncate"
                    title={sha256}
                  >
                    sha256: {sha256.slice(0, 16)}...
                  </p>
                ) : null}
              </div>
            </div>
          );
        })()}
      </div>

      {/* Sign-off */}
      <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
        <SectionLabel>Sign-off</SectionLabel>
        {c.sign_off.signed_off ? (
          <div className="flex items-center gap-2.5">
            <div className="size-9 rounded-full bg-emerald-500/15 text-emerald-400 flex items-center justify-center">
              <BadgeCheck size={18} />
            </div>
            <div>
              <p className="text-[13px] font-medium text-slate-100">
                Signed off by {c.sign_off.signed_off_by}
              </p>
              <p className="font-mono text-[11px] text-slate-400">
                {c.sign_off.signed_off_at}
              </p>
            </div>
          </div>
        ) : (
          <div>
            <div className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg bg-amber-500/8 border border-amber-500/20 mb-3">
              <AlertTriangle size={14} className="text-amber-400 shrink-0" />
              <span className="text-[12px] text-slate-300">
                Awaiting sign-off. {uncovered.length} uncovered section
                {uncovered.length === 1 ? "" : "s"} flagged.
              </span>
            </div>
            <button className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg text-[14px] font-medium bg-indigo-500 text-white hover:bg-indigo-600 transition-colors">
              <BadgeCheck size={14} />
              Sign off this run
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Artifact tables ──────────────────────────────────────────────────────────

function FeaturesTable({ runId }: { runId: string }) {
  const { data, isPending } = useFeatures(runId);
  const rows = (data ?? []) as Feature[];

  if (isPending) {
    return (
      <div className="space-y-2">
        {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-11 w-full" />)}
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[90px]">ID</TableHead>
          <TableHead>Feature</TableHead>
          <TableHead className="w-[140px]">Type</TableHead>
          <TableHead className="w-[90px]">Lane</TableHead>
          <TableHead className="w-[140px]">Assignee</TableHead>
          <TableHead className="w-[130px]">Confidence</TableHead>
          <TableHead className="w-[140px]">Source</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((f) => (
          <TableRow key={f.feature_id}>
            <TableCell><IdChip>{f.feature_id}</IdChip></TableCell>
            <TableCell className="font-medium text-slate-100">{f.name}</TableCell>
            <TableCell className="font-mono text-[12px] text-slate-400">{f.feature_type}</TableCell>
            <TableCell><LaneBadge lane={f.lane} /></TableCell>
            <TableCell><AssigneeCell name={f.assignee} /></TableCell>
            <TableCell><ConfBar value={f.confidence} /></TableCell>
            <TableCell><SrcChips src={f.source_sections} /></TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function EpicsTable({ runId }: { runId: string }) {
  const { data, isPending } = useEpics(runId);
  const rows = (data ?? []) as Epic[];

  if (isPending) {
    return (
      <div className="space-y-2">
        {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-11 w-full" />)}
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[90px]">ID</TableHead>
          <TableHead>Epic</TableHead>
          <TableHead className="w-[200px]">Features</TableHead>
          <TableHead className="w-[100px]">Review</TableHead>
          <TableHead className="w-[200px]">External ID</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((e) => (
          <TableRow key={e.epic_id}>
            <TableCell><IdChip>{e.epic_id}</IdChip></TableCell>
            <TableCell className="font-medium text-slate-100">{e.title}</TableCell>
            <TableCell>
              <div className="flex flex-wrap gap-1">
                {e.feature_ids.map((f, i) => <IdChip key={i}>{f}</IdChip>)}
              </div>
            </TableCell>
            <TableCell>
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
                  e.review_status === "AUTO_APPROVED" && "bg-emerald-500/15 text-emerald-400",
                  e.review_status === "NEEDS_REVIEW" && "bg-amber-500/15 text-amber-400",
                  e.review_status === "BLOCKED" && "bg-rose-500/15 text-rose-400",
                  !["AUTO_APPROVED","NEEDS_REVIEW","BLOCKED"].includes(e.review_status) && "bg-slate-500/15 text-slate-400",
                )}
              >
                {e.review_status}
              </span>
            </TableCell>
            <TableCell><IdChip>{e.external_id}</IdChip></TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function StoriesTable({ runId }: { runId: string }) {
  const { data, isPending } = useStories(runId);
  const rows = (data ?? []) as Story[];

  if (isPending) {
    return (
      <div className="space-y-2">
        {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-11 w-full" />)}
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[90px]">ID</TableHead>
          <TableHead className="w-[90px]">Epic</TableHead>
          <TableHead>Story</TableHead>
          <TableHead className="w-[90px]">Feature</TableHead>
          <TableHead className="w-[100px]">Review</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((s) => (
          <TableRow key={s.story_id}>
            <TableCell><IdChip>{s.story_id}</IdChip></TableCell>
            <TableCell><IdChip>{s.epic_id}</IdChip></TableCell>
            <TableCell className="font-medium text-slate-100">{s.title}</TableCell>
            <TableCell><IdChip>{s.feature_id}</IdChip></TableCell>
            <TableCell>
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
                  s.review_status === "AUTO_APPROVED" && "bg-emerald-500/15 text-emerald-400",
                  s.review_status === "NEEDS_REVIEW" && "bg-amber-500/15 text-amber-400",
                  !["AUTO_APPROVED","NEEDS_REVIEW"].includes(s.review_status) && "bg-slate-500/15 text-slate-400",
                )}
              >
                {s.review_status}
              </span>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function TasksTable({ runId }: { runId: string }) {
  const { data, isPending } = useTasks(runId);
  const rows = (data ?? []) as QATask[];

  if (isPending) {
    return (
      <div className="space-y-2">
        {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-11 w-full" />)}
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[90px]">ID</TableHead>
          <TableHead>Task</TableHead>
          <TableHead className="w-[140px]">Assignee</TableHead>
          <TableHead className="w-[90px]">Lane</TableHead>
          <TableHead className="w-[90px]">Priority</TableHead>
          <TableHead className="w-[60px]">Est</TableHead>
          <TableHead className="w-[140px]">Source</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((t) => (
          <TableRow key={t.task_id}>
            <TableCell><IdChip>{t.task_id}</IdChip></TableCell>
            <TableCell className="font-medium text-slate-100">{t.title}</TableCell>
            <TableCell><AssigneeCell name={t.assignee} /></TableCell>
            <TableCell><LaneBadge lane={t.lane} /></TableCell>
            <TableCell>
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
                  t.priority === "P0" && "bg-rose-500/15 text-rose-300",
                  t.priority === "P1" && "bg-amber-500/15 text-amber-300",
                  t.priority === "P2" && "bg-slate-500/15 text-slate-300",
                )}
              >
                {t.priority}
              </span>
            </TableCell>
            <TableCell className="font-mono text-[12.5px] text-slate-400">
              {t.estimate}
            </TableCell>
            <TableCell><SrcChips src={t.source_sections} /></TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function TestCasesTable({ runId }: { runId: string }) {
  const { data, isPending } = useTestCases(runId);
  const rows = (data ?? []) as TestCase[];

  const categoryStyle: Record<string, string> = {
    positive: "bg-emerald-500/15 text-emerald-400",
    negative: "bg-rose-500/15 text-rose-400",
    edge: "bg-amber-500/15 text-amber-400",
    integration: "bg-indigo-500/15 text-indigo-400",
  };

  if (isPending) {
    return (
      <div className="space-y-2">
        {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-11 w-full" />)}
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[100px]">ID</TableHead>
          <TableHead>Test case</TableHead>
          <TableHead className="w-[90px]">Task</TableHead>
          <TableHead className="w-[130px]">Category</TableHead>
          <TableHead className="w-[90px]">Priority</TableHead>
          <TableHead className="w-[90px]">Lane</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((tc) => (
          <TableRow key={tc.test_case_id}>
            <TableCell><IdChip>{tc.test_case_id}</IdChip></TableCell>
            <TableCell className="font-medium text-slate-100">{tc.title}</TableCell>
            <TableCell><IdChip>{tc.related_task_id}</IdChip></TableCell>
            <TableCell>
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
                  categoryStyle[tc.category] ?? "bg-slate-500/15 text-slate-400",
                )}
              >
                {tc.category}
              </span>
            </TableCell>
            <TableCell>
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
                  tc.priority === "P0" && "bg-rose-500/15 text-rose-300",
                  tc.priority === "P1" && "bg-amber-500/15 text-amber-300",
                )}
              >
                {tc.priority}
              </span>
            </TableCell>
            <TableCell><LaneBadge lane={tc.lane} /></TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function ValidationTable({ runId }: { runId: string }) {
  const { data, isPending } = useValidationIssues(runId);
  const rows = (data ?? []) as ValidationIssue[];

  if (isPending) {
    return (
      <div className="space-y-2">
        {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-11 w-full" />)}
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[240px]">Code</TableHead>
          <TableHead className="w-[100px]">Severity</TableHead>
          <TableHead className="w-[180px]">Stage</TableHead>
          <TableHead className="w-[90px]">Target</TableHead>
          <TableHead>Message</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((v) => (
          <TableRow key={v.id}>
            <TableCell className="font-mono text-[12px] text-slate-100">
              {v.code}
            </TableCell>
            <TableCell><SeverityBadge severity={v.severity} /></TableCell>
            <TableCell><IdChip>{v.stage}</IdChip></TableCell>
            <TableCell><IdChip>{v.target_id}</IdChip></TableCell>
            <TableCell className="text-[12.5px] text-slate-300 whitespace-normal">
              {v.message}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

// ─── ArtifactTabs ─────────────────────────────────────────────────────────────

function ArtifactTabs({ runId }: { runId: string }) {
  const { data: coverage } = useCoverage(runId);
  const { data: epics } = useEpics(runId);
  const { data: stories } = useStories(runId);
  const c = coverage as CoverageReport | undefined;

  const tabs = [
    { id: "features", label: "Features", count: c?.feature_count },
    { id: "epics", label: "Epics", count: (epics as unknown[] | undefined)?.length },
    { id: "stories", label: "Stories", count: (stories as unknown[] | undefined)?.length },
    { id: "tasks", label: "Tasks", count: c?.task_count },
    { id: "testcases", label: "Test Cases", count: c?.test_case_count },
    { id: "validation", label: "Validation Issues", count: c?.validation_issue_count },
  ];

  return (
    <Tabs defaultValue="features">
      <div className="flex items-center justify-between gap-3 border-b border-border">
        <TabsList variant="line" className="h-auto rounded-none bg-transparent gap-0 p-0">
          {tabs.map((t) => (
            <TabsTrigger
              key={t.id}
              value={t.id}
              className="h-[38px] px-3.5 rounded-none text-[13.5px] font-medium"
            >
              {t.label}
              {t.count != null && (
                <span className="ml-1.5 font-mono text-[11px] text-slate-500 bg-slate-500/12 px-1.5 py-0.5 rounded-full">
                  {t.count}
                </span>
              )}
            </TabsTrigger>
          ))}
        </TabsList>
        <div className="flex gap-1.5 pb-1.5">
          <button className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-lg text-[12.5px] font-medium text-slate-400 hover:bg-slate-800 hover:text-slate-100 transition-colors">
            Filter
          </button>
          <button className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-lg text-[12.5px] font-medium text-slate-400 hover:bg-slate-800 hover:text-slate-100 transition-colors">
            Search
          </button>
        </div>
      </div>

      <div className="mt-3.5">
        <TabsContent value="features">
          <FeaturesTable runId={runId} />
        </TabsContent>
        <TabsContent value="epics">
          <EpicsTable runId={runId} />
        </TabsContent>
        <TabsContent value="stories">
          <StoriesTable runId={runId} />
        </TabsContent>
        <TabsContent value="tasks">
          <TasksTable runId={runId} />
        </TabsContent>
        <TabsContent value="testcases">
          <TestCasesTable runId={runId} />
        </TabsContent>
        <TabsContent value="validation">
          <ValidationTable runId={runId} />
        </TabsContent>
      </div>
    </Tabs>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

function flattenReviewQueue(queue?: ReviewQueue): ReviewQueueItem[] {
  return queue?.groups.flatMap((group) => group.items) ?? [];
}

function isSignedOff(run: Run): boolean {
  const coverageSignOff = run.coverage_report?.sign_off as
    | { signed_off?: boolean }
    | undefined;
  return Boolean(run.signed_off_at || coverageSignOff?.signed_off);
}

function NextStagePanel({ run }: { run: Run }) {
  const stage = run.current_stage;
  const queryClient = useQueryClient();
  const queueRef = useRef<HTMLDivElement | null>(null);
  const [bulkAction, setBulkAction] = useState<string | null>(null);

  const hil1Enabled = stage === "S2_AGENT_A" || stage === "S3_VALIDATION_A";
  const hil2Enabled = stage === "S4_AGENT_B" || stage === "S5_VALIDATION_B_SYNC";
  const hil3Enabled = stage === "S6_AGENT_C" || stage === "S7_VALIDATION_C_SYNC";

  const hil0Questions = useHil0Questions(run.id, {
    enabled: stage === "S1_CONTEXT_LOADER",
  });
  const hil1Queue = useReviewQueue(run.id, "HIL-1", { enabled: hil1Enabled });
  const hil2Queue = useReviewQueue(run.id, "HIL-2", { enabled: hil2Enabled });
  const hil3Queue = useReviewQueue(run.id, "HIL-3", { enabled: hil3Enabled });

  const handleStageError = (error: ApiError) => {
    if (error.code === "hil_gate_blocked") {
      window.setTimeout(() => queueRef.current?.scrollIntoView({ block: "center" }), 0);
    }
    if (error.code === "wrong_stage") {
      queryClient.invalidateQueries({ queryKey: queryKeys.run(run.id) });
    }
  };

  const loadContext = useLoadContext(run.id, {
    onError: (error) => handleStageError(error),
  });
  const runAgentA = useRunAgentA(run.id, {
    onError: (error) => handleStageError(error),
  });
  const runAgentB = useRunAgentB(run.id, {
    onError: (error) => handleStageError(error),
  });
  const runAgentC = useRunAgentC(run.id, {
    onError: (error) => handleStageError(error),
  });
  const finalizeRun = useFinalizeRun(run.id, {
    onError: (error) => handleStageError(error),
  });
  const signOffRun = useSignOffRun(run.id);
  const resolveHil0 = useResolveHil0Question(run.id);
  const resolveHil0Bulk = useResolveHil0Questions(run.id);
  const createDecision = useCreateReviewDecision();

  const openHil0Questions = ((hil0Questions.data ?? []) as HIL0Question[]).filter(
    (question) => question.status === "OPEN",
  );

  const activeTier: HilTier | null = hil1Enabled
    ? "HIL-1"
    : hil2Enabled
      ? "HIL-2"
      : hil3Enabled
        ? "HIL-3"
        : null;
  const activeQueue =
    activeTier === "HIL-1"
      ? hil1Queue
      : activeTier === "HIL-2"
        ? hil2Queue
        : activeTier === "HIL-3"
          ? hil3Queue
          : null;
  const reviewItems = flattenReviewQueue(activeQueue?.data);

  const stageBusy =
    loadContext.isPending ||
    runAgentA.isPending ||
    runAgentB.isPending ||
    runAgentC.isPending ||
    finalizeRun.isPending ||
    signOffRun.isPending ||
    resolveHil0Bulk.isPending ||
    Boolean(bulkAction);
  const queuePending = Boolean(activeTier && activeQueue?.isPending);
  const killSwitch = run.session_memory?.kill_switch as
    | { tripped?: boolean; s1_risk_count?: number; threshold?: number }
    | undefined;

  const approveItems = async (items: ReviewQueueItem[]) => {
    if (!items.length) return;
    setBulkAction(`approve-${activeTier}`);
    try {
      for (const item of items) {
        await createDecision.mutateAsync({
          run_id: run.id,
          target_type: item.target_type,
          target_id: item.target_id,
          decision: "APPROVED",
          reviewer: item.reviewer,
        });
      }
      toast.success(`${activeTier} queue approved`, {
        description: `${items.length} item(s) cleared.`,
      });
    } finally {
      setBulkAction(null);
    }
  };

  const resolveAllHil0 = async () => {
    if (!openHil0Questions.length) return;
    setBulkAction("resolve-hil0");
    try {
      await resolveHil0Bulk.mutateAsync({
        resolutions: openHil0Questions.map((question) => ({
          question_id: question.id,
          action: "proceed_with_flag",
          reviewer: "QA Lead",
          response: "Proceeding with a confidence flag for the demo walkthrough.",
        })),
      });
    } finally {
      setBulkAction(null);
    }
  };

  const pendingIcon = stageBusy ? <Loader2 size={14} className="animate-spin" /> : null;
  let title = "Pipeline complete";
  let description = "This run has no further stage action.";
  let actionLabel: string | null = null;
  let ActionIcon: React.ElementType = BadgeCheck;
  let onAction: (() => void) | null = null;
  let tone = "border-indigo-500/30 bg-indigo-500/8";

  if (run.status === "FAILED" || killSwitch?.tripped) {
    title = "Pipeline halted";
    description = "The kill switch or a stage failure stopped this run before completion.";
    ActionIcon = AlertTriangle;
    tone = "border-rose-500/30 bg-rose-500/8";
  } else if (stage === "S0_TRIGGER") {
    title = "Next: Load Context";
    description = "Register the GDD version, parse sections, and prepare HIL-0 questions.";
    actionLabel = "Load Context";
    ActionIcon = FileText;
    onAction = () => loadContext.mutate(undefined);
  } else if (stage === "S1_CONTEXT_LOADER") {
    if (openHil0Questions.length > 0) {
      title = "HIL-0 questions are open";
      description = "Resolve clarification prompts before handing the parsed GDD to Agent A.";
      actionLabel = `Proceed with flag (${openHil0Questions.length})`;
      ActionIcon = ListChecks;
      onAction = () => void resolveAllHil0();
      tone = "border-amber-500/30 bg-amber-500/8";
    } else {
      title = "Next: Run Agent A";
      description = "Generate feature inventory from actionable GDD sections and run Validation A.";
      actionLabel = "Run Agent A";
      ActionIcon = Workflow;
      onAction = () => runAgentA.mutate();
    }
  } else if (hil1Enabled) {
    if (reviewItems.length > 0 || queuePending) {
      title = "HIL-1 review required";
      description = "Clear feature review items before Agent B can plan epics, stories, and tasks.";
      actionLabel = reviewItems.length ? `Approve all (${reviewItems.length})` : "Loading queue";
      ActionIcon = ListChecks;
      onAction = () => void approveItems(reviewItems);
      tone = "border-amber-500/30 bg-amber-500/8";
    } else {
      title = "Next: Run Agent B";
      description = "Plan QA epics, stories, and tasks, then sync approved scope to Notion.";
      actionLabel = "Run Agent B";
      ActionIcon = Workflow;
      onAction = () => runAgentB.mutate();
    }
  } else if (hil2Enabled) {
    if (reviewItems.length > 0 || queuePending) {
      title = "HIL-2 review required";
      description = "Clear task review items before Agent C can generate test cases.";
      actionLabel = reviewItems.length ? `Approve all (${reviewItems.length})` : "Loading queue";
      ActionIcon = ListChecks;
      onAction = () => void approveItems(reviewItems);
      tone = "border-amber-500/30 bg-amber-500/8";
    } else {
      title = "Next: Run Agent C";
      description = "Generate test cases, run Validation C, and sync ready cases to Notion.";
      actionLabel = "Run Agent C";
      ActionIcon = Workflow;
      onAction = () => runAgentC.mutate();
    }
  } else if (hil3Enabled) {
    if (reviewItems.length > 0 || queuePending) {
      title = "HIL-3 review required";
      description = "Clear flagged test cases before final coverage can be produced.";
      actionLabel = reviewItems.length ? `Approve all (${reviewItems.length})` : "Loading queue";
      ActionIcon = ListChecks;
      onAction = () => void approveItems(reviewItems);
      tone = "border-amber-500/30 bg-amber-500/8";
    } else {
      title = "Next: Finalize";
      description = "Build the final coverage report and mark the run completed.";
      actionLabel = "Finalize";
      ActionIcon = BadgeCheck;
      onAction = () => finalizeRun.mutate();
    }
  } else if (stage === "FINAL_COVERAGE") {
    if (isSignedOff(run)) {
      title = "Signed off";
      description = `Final coverage was signed off by ${run.signed_off_by ?? "QA Lead"}.`;
      ActionIcon = BadgeCheck;
      tone = "border-emerald-500/30 bg-emerald-500/8";
    } else {
      title = "Next: Sign off";
      description = "The pipeline is complete. Record QA Lead sign-off for the final report.";
      actionLabel = "Sign off";
      ActionIcon = BadgeCheck;
      onAction = () => signOffRun.mutate({ reviewer: "QA Lead" });
      tone = "border-emerald-500/30 bg-emerald-500/8";
    }
  }

  const disabled =
    stageBusy ||
    queuePending ||
    !onAction ||
    (Boolean(activeTier) && reviewItems.length === 0 && actionLabel === "Loading queue");

  return (
    <div className={cn("mb-5 rounded-xl border p-4", tone)}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="mb-1.5 flex items-center gap-2 text-[12px] font-medium uppercase tracking-[0.06em] text-indigo-300">
            <ActionIcon size={14} />
            Next stage
            <IdChip>{stage}</IdChip>
          </div>
          <p className="text-[13.5px] font-medium text-slate-100">{title}</p>
          <p className="mt-1 text-[12.5px] text-slate-400">{description}</p>
        </div>

        {actionLabel ? (
          <button
            type="button"
            onClick={onAction ?? undefined}
            disabled={disabled}
            className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg bg-indigo-500 px-3.5 text-[14px] font-medium text-white transition-colors hover:bg-indigo-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {pendingIcon ?? <ActionIcon size={14} />}
            {actionLabel}
          </button>
        ) : null}
      </div>

      {openHil0Questions.length > 0 && stage === "S1_CONTEXT_LOADER" ? (
        <div className="mt-4 divide-y divide-border rounded-lg border border-border bg-slate-950/25">
          {openHil0Questions.map((question) => (
            <div key={question.id} className="flex items-start justify-between gap-3 px-3 py-2.5">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <IdChip>{question.section_id}</IdChip>
                  <span className="text-[13px] font-medium text-slate-100">
                    {question.title}
                  </span>
                </div>
                <p className="mt-1 text-[12.5px] text-slate-400">{question.question}</p>
              </div>
              <button
                type="button"
                disabled={resolveHil0.isPending || Boolean(bulkAction)}
                onClick={() =>
                  resolveHil0.mutate({
                    question_id: question.id,
                    action: "proceed_with_flag",
                    reviewer: "QA Lead",
                    response: "Proceeding with a confidence flag for the demo walkthrough.",
                  })
                }
                className="inline-flex h-7 shrink-0 items-center rounded-md border border-slate-700 px-2.5 text-[12px] font-medium text-slate-300 hover:bg-slate-800 disabled:opacity-60"
              >
                Proceed
              </button>
            </div>
          ))}
        </div>
      ) : null}

      {activeTier && (reviewItems.length > 0 || queuePending) ? (
        <div ref={queueRef} className="mt-4 divide-y divide-border rounded-lg border border-border bg-slate-950/25">
          {queuePending ? (
            <div className="space-y-2 p-3">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : (
            reviewItems.map((item) => (
              <div key={`${item.target_type}-${item.target_id}`} className="flex items-center justify-between gap-3 px-3 py-2.5">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <IdChip>{item.target_id}</IdChip>
                    <LaneBadge lane={item.lane} />
                    <StatusBadge status={item.review_status} />
                  </div>
                  <p className="mt-1 truncate text-[13px] font-medium text-slate-100">
                    {item.title}
                  </p>
                  <p className="mt-0.5 text-[11.5px] text-slate-500">
                    {item.reviewer}
                    {item.feature_id ? ` - ${item.feature_id}` : ""}
                    {item.epic_id ? ` - ${item.epic_id}` : ""}
                  </p>
                </div>
                <div className="flex shrink-0 gap-1.5">
                  <button
                    type="button"
                    disabled={createDecision.isPending || Boolean(bulkAction)}
                    onClick={() =>
                      createDecision.mutate({
                        run_id: run.id,
                        target_type: item.target_type,
                        target_id: item.target_id,
                        decision: "APPROVED",
                        reviewer: item.reviewer,
                      })
                    }
                    className="inline-flex h-7 items-center rounded-md bg-emerald-500/15 px-2.5 text-[12px] font-medium text-emerald-300 hover:bg-emerald-500/25 disabled:opacity-60"
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    disabled={createDecision.isPending || Boolean(bulkAction)}
                    onClick={() =>
                      createDecision.mutate({
                        run_id: run.id,
                        target_type: item.target_type,
                        target_id: item.target_id,
                        decision: "REJECTED",
                        reviewer: item.reviewer,
                      })
                    }
                    className="inline-flex h-7 items-center rounded-md border border-slate-700 px-2.5 text-[12px] font-medium text-slate-300 hover:bg-slate-800 disabled:opacity-60"
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}

export default function RunDashboardPage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;

  const { data: runData, isPending: runPending } = useRun(runId);
  const run = runData as Run | undefined;

  return (
    <div className="p-6 max-w-[1440px] w-full mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-[18px]">
        <div className="min-w-0">
          {/* Breadcrumb */}
          <div className="flex items-center gap-1.5 mb-2 font-mono text-[11.5px] text-slate-500">
            <span>{run?.project_id ?? runId.split("_")[0]}</span>
            <ChevronRight size={11} />
            <span>runs</span>
            <ChevronRight size={11} />
            <IdChip>{runId}</IdChip>
          </div>

          <h1 className="text-[24px] font-semibold tracking-tight text-slate-100 flex items-center flex-wrap gap-2.5">
            Run Dashboard
            {runPending ? (
              <InlineSkeleton className="h-5 w-24" />
            ) : (
              <>
                <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium bg-indigo-500/18 text-indigo-300">
                  {run?.mode ?? "—"}
                </span>
                <StatusBadge status={run?.status ?? "PENDING"} />
              </>
            )}
          </h1>

          <div className="mt-1.5 text-[13px] text-slate-400">
            {runPending ? (
              <InlineSkeleton className="h-3 w-64" />
            ) : (
              <>
                {run?.session_memory &&
                  "source_version_id" in run.session_memory && (
                    <>
                      GDD{" "}
                      <span className="font-mono">
                        {run.session_memory.source_version_id as string}
                      </span>{" "}
                      ·{" "}
                    </>
                  )}
                {run?.finished_at
                  ? `finished ${new Date(run.finished_at).toISOString().replace("T", " ").slice(0, 19)} UTC`
                  : run?.created_at
                    ? `started ${new Date(run.created_at).toISOString().replace("T", " ").slice(0, 19)} UTC`
                    : "—"}
              </>
            )}
          </div>
        </div>

        <div className="flex gap-2 shrink-0">
          <span className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg text-[13px] font-medium text-slate-300 border border-slate-700 bg-slate-950/30">
            <Workflow size={14} />
            {run?.current_stage ?? "Loading"}
          </span>
        </div>
      </div>

      {/* Kill switch banner */}
      {(() => {
        const ks = run?.session_memory?.kill_switch as
          | { tripped?: boolean; s1_risk_count?: number; threshold?: number }
          | undefined;
        return ks?.tripped ? (
          <div className="mb-5 flex items-center gap-3 px-4 py-3 rounded-xl bg-rose-500/10 border border-rose-500/30">
            <AlertTriangle size={16} className="text-rose-400 shrink-0" />
            <span className="text-[13px] text-rose-300 font-medium">
              Kill switch tripped — pipeline halted after{" "}
              {ks.s1_risk_count} S1 risk event
              {ks.s1_risk_count !== 1 ? "s" : ""}{" "}
              (threshold: {ks.threshold}).
            </span>
          </div>
        ) : null;
      })()}

      {run ? <NextStagePanel run={run} /> : null}

      {/* Agent runs */}
      <div className="mb-5">
        <AgentRunsPanel runId={runId} />
      </div>

      {/* Two-column: timeline + coverage */}
      <div
        className="grid gap-5 mb-6"
        style={{ gridTemplateColumns: "minmax(0, 1.35fr) minmax(0, 1fr)" }}
      >
        <TimelinePanel runId={runId} />
        <CoveragePanel runId={runId} />
      </div>

      {/* Artifact tabs */}
      <ArtifactTabs runId={runId} />
    </div>
  );
}
