"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BadgeCheck,
  Database,
  Folder,
  GitBranch,
  ListChecks,
  Search,
  Settings,
  ShieldAlert,
  Workflow,
} from "lucide-react";

import { useProvidersStatus } from "@/lib/queries";
import type { ProviderState } from "@/lib/types";
import { cn } from "@/lib/utils";

function currentRunId(pathname: string): string | null {
  return pathname.match(/\/runs\/([^/]+)/)?.[1] ?? null;
}

function shortRunId(runId: string): string {
  return runId.length > 12 ? `${runId.slice(0, 8)}...` : runId;
}

function SidebarItem({
  href,
  label,
  icon: Icon,
  active,
  badge,
}: {
  href: string;
  label: string;
  icon: React.ElementType;
  active: boolean;
  badge?: string;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex h-8 w-full items-center gap-2 rounded-lg px-2.5 text-[13.5px] font-medium transition-colors",
        active
          ? "bg-indigo-500/14 text-indigo-300"
          : "text-slate-200 hover:bg-slate-800/70 hover:text-slate-50",
      )}
    >
      <Icon className="size-4 shrink-0" />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {badge ? (
        <span className="rounded-full bg-slate-800 px-1.5 py-0.5 font-mono text-[11px] leading-none text-slate-400">
          {badge}
        </span>
      ) : null}
    </Link>
  );
}

function SidebarSection({
  title,
  right,
  children,
}: {
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between px-2.5 text-[10.5px] font-medium uppercase text-slate-500">
        <span>{title}</span>
        {right}
      </div>
      <div className="flex flex-col gap-0.5">{children}</div>
    </div>
  );
}

function ProviderPill({
  label,
  fallback,
  state,
  loading,
  error,
}: {
  label: string;
  fallback: string;
  state?: ProviderState;
  loading: boolean;
  error: boolean;
}) {
  const ready = state?.credentials_ready;
  const provider = state?.provider ?? (loading ? "checking" : fallback);
  const unhealthy = error || ready === false;

  return (
    <span
      className={cn(
        "inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 text-[12.5px] font-medium",
        unhealthy
          ? "bg-rose-500/12 text-rose-300"
          : ready || !state
            ? "bg-emerald-500/12 text-emerald-400"
            : "bg-slate-800 text-slate-300",
      )}
      title={`${label}: ${provider}`}
    >
      <span className="size-1.5 rounded-full bg-current" />
      {label} {provider}
    </span>
  );
}

function ProviderStatusPills() {
  const { data, isPending, isError } = useProvidersStatus({
    retry: 1,
    staleTime: 60_000,
  });

  return (
    <div className="hidden items-center gap-2 md:flex">
      <ProviderPill
        label="AI"
        fallback="mock"
        state={data?.ai}
        loading={isPending}
        error={isError}
      />
      <ProviderPill
        label="Notion"
        fallback="mock"
        state={data?.notion}
        loading={isPending}
        error={isError}
      />
      <ProviderPill
        label="repo"
        fallback="memory"
        state={data?.repository}
        loading={isPending}
        error={isError}
      />
    </div>
  );
}

function Sidebar({ pathname }: { pathname: string }) {
  const runId = currentRunId(pathname);
  const runBase = runId ? `/runs/${runId}` : "/runs";

  return (
    <aside className="hidden h-screen w-64 shrink-0 flex-col border-r border-border bg-background p-3 lg:flex">
      <div className="mb-4 flex items-center gap-2.5 px-1.5 py-1">
        <div className="flex size-7 items-center justify-center rounded-lg bg-indigo-500 font-mono text-[13px] font-semibold text-white">
          SR
        </div>
        <div className="min-w-0 leading-tight">
          <div className="text-[13.5px] font-semibold text-slate-50">
            SUN.RISER
          </div>
          <div className="text-[11px] text-slate-400">QA Workflow</div>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-4">
        <SidebarSection title="Workspace">
          <SidebarItem
            href="/projects"
            label="Projects"
            icon={Folder}
            active={pathname.startsWith("/projects")}
          />
          <SidebarItem
            href="/runs"
            label="Runs"
            icon={Workflow}
            active={pathname === "/runs"}
          />
        </SidebarSection>

        {runId ? (
          <SidebarSection
            title="Current run"
            right={
              <span className="rounded-md bg-slate-800 px-1.5 py-0.5 font-mono text-[11px] leading-none text-slate-400">
                {shortRunId(runId)}
              </span>
            }
          >
            <SidebarItem
              href={runBase}
              label="Dashboard"
              icon={GitBranch}
              active={pathname === runBase}
            />
            <SidebarItem
              href={`${runBase}/hil/HIL-1`}
              label="HIL queue"
              icon={ListChecks}
              active={pathname.includes("/hil/")}
              badge="2"
            />
            <SidebarItem
              href={`${runBase}/sync-log`}
              label="Sync log"
              icon={Database}
              active={pathname.endsWith("/sync-log")}
            />
            <SidebarItem
              href={`${runBase}/risk`}
              label="Risk"
              icon={ShieldAlert}
              active={pathname.endsWith("/risk")}
              badge="1"
            />
            <SidebarItem
              href={`${runBase}/sign-off`}
              label="Sign off"
              icon={BadgeCheck}
              active={pathname.endsWith("/sign-off")}
            />
          </SidebarSection>
        ) : null}
      </div>

      <div className="mt-auto">
        <SidebarItem
          href="/settings"
          label="Settings"
          icon={Settings}
          active={pathname.startsWith("/settings")}
        />
        <div className="mt-2 flex items-center gap-2 border-t border-border px-1.5 py-3">
          <div className="flex size-6 items-center justify-center rounded-full bg-slate-700 text-[11px] font-semibold text-slate-100">
            NA
          </div>
          <div className="min-w-0 leading-tight">
            <div className="truncate text-[12.5px] font-medium text-slate-100">
              Ngoc Anh
            </div>
            <div className="text-[11px] text-slate-400">QA Lead</div>
          </div>
        </div>
      </div>
    </aside>
  );
}

function Header() {
  return (
    <header className="flex h-14 shrink-0 items-center justify-end gap-3 border-b border-border bg-background px-6">
      <ProviderStatusPills />
      <div className="hidden h-5 w-px bg-border md:block" />
      <button className="inline-flex h-8 min-w-[184px] items-center gap-2 rounded-lg border border-slate-700 bg-transparent px-2.5 text-left text-[13px] font-medium text-slate-200 transition-colors hover:bg-slate-800/70">
        <Search className="size-4 text-slate-300" />
        <span className="min-w-0 flex-1 truncate">Search...</span>
        <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[11px] leading-none text-slate-400">
          Ctrl K
        </span>
      </button>
    </header>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex h-screen min-h-0 bg-background text-foreground">
      <Sidebar pathname={pathname} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="min-h-0 flex-1 overflow-auto bg-background">
          {children}
        </main>
      </div>
    </div>
  );
}
