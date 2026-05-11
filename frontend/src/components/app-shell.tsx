"use client";

import { useState, type ElementType, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BadgeCheck,
  Database,
  Folder,
  GitBranch,
  ListChecks,
  Menu,
  Search,
  Settings,
  ShieldAlert,
  Workflow,
} from "lucide-react";

import { API_BASE } from "@/lib/api";
import { useProvidersStatus } from "@/lib/queries";
import type { ProviderState } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";

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
  onNavigate,
}: {
  href: string;
  label: string;
  icon: ElementType;
  active: boolean;
  badge?: string;
  onNavigate?: () => void;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      onClick={onNavigate}
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
  right?: ReactNode;
  children: ReactNode;
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
  onClick,
}: {
  label: string;
  fallback: string;
  state?: ProviderState;
  loading: boolean;
  error: boolean;
  onClick: () => void;
}) {
  const ready = state?.credentials_ready;
  const provider = state?.provider ?? (loading ? "checking" : fallback);
  const unhealthy = error || ready === false;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 text-[12.5px] font-medium transition-colors hover:bg-slate-700/70 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
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
    </button>
  );
}

function ProviderStatusPills() {
  const [open, setOpen] = useState(false);
  const { data, isPending, isError } = useProvidersStatus({
    retry: 1,
    staleTime: 60_000,
  });

  const rows = [
    { label: "AI", fallback: "mock", state: data?.ai },
    { label: "Notion", fallback: "mock", state: data?.notion },
    { label: "Repository", fallback: "memory", state: data?.repository },
  ];

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <div className="hidden items-center gap-2 md:flex">
        <ProviderPill
          label="AI"
          fallback="mock"
          state={data?.ai}
          loading={isPending}
          error={isError}
          onClick={() => setOpen(true)}
        />
        <ProviderPill
          label="Notion"
          fallback="mock"
          state={data?.notion}
          loading={isPending}
          error={isError}
          onClick={() => setOpen(true)}
        />
        <ProviderPill
          label="repo"
          fallback="memory"
          state={data?.repository}
          loading={isPending}
          error={isError}
          onClick={() => setOpen(true)}
        />
      </div>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="md:hidden"
        title="Provider status"
        onClick={() => setOpen(true)}
      >
        <Database className="size-4" />
        <span className="sr-only">Provider status</span>
      </Button>
      <DialogContent className="max-w-[560px] gap-4 bg-slate-950">
        <DialogHeader>
          <DialogTitle>Provider status</DialogTitle>
        </DialogHeader>
        <div className="overflow-hidden rounded-lg border border-border">
          <div className="grid grid-cols-[1fr_1fr_96px] border-b border-border bg-slate-900/70 px-3 py-2 text-[11px] font-medium uppercase text-slate-500">
            <span>Service</span>
            <span>Provider</span>
            <span>Ready</span>
          </div>
          {rows.map((row) => {
            const ready = row.state?.credentials_ready;
            const unhealthy = isError || ready === false;
            return (
              <div
                key={row.label}
                className="grid grid-cols-[1fr_1fr_96px] items-center border-b border-border px-3 py-2.5 text-[13px] last:border-b-0"
              >
                <span className="font-medium text-slate-100">{row.label}</span>
                <span className="font-mono text-slate-300">
                  {row.state?.provider ?? (isPending ? "checking" : row.fallback)}
                </span>
                <span
                  className={cn(
                    "w-fit rounded-full px-2 py-0.5 text-[11px] font-medium",
                    unhealthy
                      ? "bg-rose-500/12 text-rose-300"
                      : "bg-emerald-500/12 text-emerald-400",
                  )}
                >
                  {unhealthy ? "review" : "ready"}
                </span>
              </div>
            );
          })}
        </div>
        <div className="rounded-lg border border-border bg-slate-900/40 p-3 text-[12.5px] text-slate-400">
          <div className="mb-1 font-medium text-slate-200">API base</div>
          <code className="break-all font-mono text-slate-300">{API_BASE}</code>
          {isError ? (
            <div className="mt-2 text-rose-300">
              Provider status endpoint is currently unreachable.
            </div>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function SidebarContent({
  pathname,
  onNavigate,
}: {
  pathname: string;
  onNavigate?: () => void;
}) {
  const runId = currentRunId(pathname);
  const runBase = runId ? `/runs/${runId}` : "/runs";

  return (
    <>
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
            onNavigate={onNavigate}
          />
          <SidebarItem
            href="/runs"
            label="Runs"
            icon={Workflow}
            active={pathname === "/runs"}
            onNavigate={onNavigate}
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
              onNavigate={onNavigate}
            />
            <SidebarItem
              href={`${runBase}/hil/HIL-1`}
              label="HIL queue"
              icon={ListChecks}
              active={pathname.includes("/hil/")}
              badge="2"
              onNavigate={onNavigate}
            />
            <SidebarItem
              href={`${runBase}/sync-log`}
              label="Sync log"
              icon={Database}
              active={pathname.endsWith("/sync-log")}
              onNavigate={onNavigate}
            />
            <SidebarItem
              href={`${runBase}/risk`}
              label="Risk"
              icon={ShieldAlert}
              active={pathname.endsWith("/risk")}
              badge="1"
              onNavigate={onNavigate}
            />
            <SidebarItem
              href={`${runBase}/sign-off`}
              label="Sign off"
              icon={BadgeCheck}
              active={pathname.endsWith("/sign-off")}
              onNavigate={onNavigate}
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
          onNavigate={onNavigate}
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
    </>
  );
}

function Sidebar({ pathname }: { pathname: string }) {
  return (
    <aside className="hidden h-screen w-64 shrink-0 flex-col border-r border-border bg-background p-3 lg:flex">
      <SidebarContent pathname={pathname} />
    </aside>
  );
}

function MobileSidebar({ pathname }: { pathname: string }) {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            title="Open navigation"
          />
        }
      >
        <Menu className="size-4" />
        <span className="sr-only">Open navigation</span>
      </SheetTrigger>
      <SheetContent
        side="left"
        className="data-[side=left]:w-[280px] data-[side=left]:max-w-[85vw] border-r border-border bg-background p-0"
      >
        <SheetHeader className="sr-only">
          <SheetTitle>Navigation</SheetTitle>
          <SheetDescription>Primary workspace navigation</SheetDescription>
        </SheetHeader>
        <div className="flex h-full flex-col p-3">
          <SidebarContent pathname={pathname} onNavigate={() => setOpen(false)} />
        </div>
      </SheetContent>
    </Sheet>
  );
}

function Header({ pathname }: { pathname: string }) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background px-3 sm:px-6">
      <MobileSidebar pathname={pathname} />
      <div className="ml-auto flex min-w-0 items-center gap-3">
        <ProviderStatusPills />
        <div className="hidden h-5 w-px bg-border md:block" />
        <button className="hidden h-8 min-w-[184px] items-center gap-2 rounded-lg border border-slate-700 bg-transparent px-2.5 text-left text-[13px] font-medium text-slate-200 transition-colors hover:bg-slate-800/70 sm:inline-flex">
          <Search className="size-4 text-slate-300" />
          <span className="min-w-0 flex-1 truncate">Search...</span>
          <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[11px] leading-none text-slate-400">
            Ctrl K
          </span>
        </button>
      </div>
    </header>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex h-screen min-h-0 bg-background text-foreground">
      <Sidebar pathname={pathname} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header pathname={pathname} />
        <main className="min-h-0 flex-1 overflow-auto bg-background">
          {children}
        </main>
      </div>
    </div>
  );
}
