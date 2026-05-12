"use client";

import { GitMerge, GitPullRequest, Save } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";
import { useEpics, useFeatures } from "@/lib/queries";
import { useMergeEpics, useSplitEpic, useUpdateEpic } from "@/lib/mutations";
import type { Epic, Feature, Run } from "@/lib/types";

export function EpicReviewPanel({ run }: { run: Run }) {
  const editable = run.current_stage === "S4_1_AGENT_B_EPICS";
  const epicsQuery = useEpics(run.id);
  const featuresQuery = useFeatures(run.id);
  const updateEpic = useUpdateEpic(run.id);
  const mergeEpics = useMergeEpics(run.id);
  const splitEpic = useSplitEpic(run.id);
  const epics = epicsQuery.data ?? [];
  const featuresById = new Map((featuresQuery.data ?? []).map((feature) => [feature.feature_id, feature]));
  const [draftTitles, setDraftTitles] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<string[]>([]);

  const saveTitle = (epic: Epic) => {
    const title = draftTitles[epic.epic_id]?.trim();
    if (!title || title === epic.title) return;
    updateEpic.mutate({ epicId: epic.epic_id, body: { title } });
  };

  const mergeSelected = () => {
    const picked = epics.filter((epic) => selected.includes(epic.epic_id));
    if (picked.length < 2) return;
    mergeEpics.mutate({
      source_epic_ids: picked.map((epic) => epic.epic_id),
      target_title: picked[0].title,
      target_description: picked.map((epic) => epic.title).join(" / "),
    });
    setSelected([]);
  };

  const splitSelected = () => {
    const epic = epics.find((item) => item.epic_id === selected[0]);
    if (!epic || selected.length !== 1 || epic.feature_ids.length < 2) return;
    const midpoint = Math.ceil(epic.feature_ids.length / 2);
    const first = epic.feature_ids.slice(0, midpoint);
    const second = epic.feature_ids.slice(midpoint);
    splitEpic.mutate({
      epic_id: epic.epic_id,
      splits: [
        {
          title: `${epic.title} A`,
          description: epic.description,
          feature_ids: first,
        },
        {
          title: `${epic.title} B`,
          description: epic.description,
          feature_ids: second,
        },
      ],
    });
    setSelected([]);
  };

  if (!epics.length && !epicsQuery.isPending) {
    return null;
  }

  return (
    <section className="mb-5 rounded-xl border border-border bg-card">
      <div className="flex flex-col gap-3 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-[13.5px] font-semibold text-slate-100">Epic review</h2>
          <p className="mt-0.5 text-[12px] text-slate-500">
            {editable ? "Editable before story planning" : "Locked after story planning starts"}
          </p>
        </div>
        {editable ? (
          <div className="flex gap-2">
            <button
              type="button"
              disabled={selected.length < 2 || mergeEpics.isPending}
              onClick={mergeSelected}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-700 px-3 text-[12px] font-medium text-slate-300 hover:bg-slate-800 disabled:opacity-50"
            >
              <GitMerge size={13} />
              Merge
            </button>
            <button
              type="button"
              disabled={selected.length !== 1 || splitEpic.isPending}
              onClick={splitSelected}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-700 px-3 text-[12px] font-medium text-slate-300 hover:bg-slate-800 disabled:opacity-50"
            >
              <GitPullRequest size={13} />
              Split
            </button>
          </div>
        ) : null}
      </div>

      <div className="grid gap-3 p-3 lg:grid-cols-2">
        {epics.map((epic) => (
          <EpicCard
            key={epic.epic_id}
            epic={epic}
            editable={editable}
            selected={selected.includes(epic.epic_id)}
            title={draftTitles[epic.epic_id] ?? epic.title}
            featuresById={featuresById}
            saving={updateEpic.isPending}
            onSelect={(checked) =>
              setSelected((current) =>
                checked
                  ? [...current, epic.epic_id]
                  : current.filter((id) => id !== epic.epic_id)
              )
            }
            onTitle={(title) =>
              setDraftTitles((current) => ({ ...current, [epic.epic_id]: title }))
            }
            onSave={() => saveTitle(epic)}
          />
        ))}
      </div>
    </section>
  );
}

function EpicCard({
  epic,
  editable,
  selected,
  title,
  featuresById,
  saving,
  onSelect,
  onTitle,
  onSave,
}: {
  epic: Epic;
  editable: boolean;
  selected: boolean;
  title: string;
  featuresById: Map<string, Feature>;
  saving: boolean;
  onSelect: (checked: boolean) => void;
  onTitle: (title: string) => void;
  onSave: () => void;
}) {
  return (
    <article
      className={cn(
        "rounded-lg border p-3",
        selected ? "border-indigo-400/50 bg-indigo-500/8" : "border-border bg-slate-950/25"
      )}
    >
      <div className="flex items-start gap-2">
        {editable ? (
          <input
            type="checkbox"
            checked={selected}
            onChange={(event) => onSelect(event.target.checked)}
            className="mt-1 size-4 accent-indigo-500"
            aria-label={`Select ${epic.title}`}
          />
        ) : null}
        <div className="min-w-0 flex-1">
          {editable ? (
            <div className="flex gap-2">
              <input
                value={title}
                onChange={(event) => onTitle(event.target.value)}
                className="h-8 min-w-0 flex-1 rounded-md border border-slate-700 bg-slate-950 px-2.5 text-[13px] font-medium text-slate-100 outline-none focus:border-indigo-400"
              />
              <button
                type="button"
                disabled={saving || title.trim() === epic.title}
                onClick={onSave}
                className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-indigo-500 text-white hover:bg-indigo-600 disabled:opacity-50"
                aria-label={`Save ${epic.title}`}
              >
                <Save size={13} />
              </button>
            </div>
          ) : (
            <h3 className="truncate text-[13px] font-semibold text-slate-100">{epic.title}</h3>
          )}
          <p className="mt-2 line-clamp-2 text-[12px] text-slate-400">{epic.description}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {epic.feature_ids.map((featureId) => (
              <span
                key={featureId}
                className="rounded-full bg-slate-500/12 px-2 py-0.5 font-mono text-[11px] text-slate-300"
                title={featuresById.get(featureId)?.name}
              >
                {featureId}
              </span>
            ))}
          </div>
        </div>
      </div>
    </article>
  );
}
