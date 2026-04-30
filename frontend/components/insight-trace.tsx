"use client";

import { useState } from "react";
import { ChevronDown, Cpu, Database, FileText, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import type { TraceEntry } from "@/lib/api";

const NODE_META: Record<
  string,
  { label: string; icon: React.ElementType; color: string }
> = {
  enricher: { label: "Enricher", icon: Database, color: "text-sky-600" },
  analyzer: { label: "Analyzer", icon: Search, color: "text-violet-600" },
  recommender: { label: "Recommender", icon: Cpu, color: "text-orange-600" },
  composer: { label: "Composer", icon: FileText, color: "text-emerald-600" },
};

function nodeMeta(node: string) {
  return (
    NODE_META[node] ?? {
      label: node,
      icon: FileText,
      color: "text-zinc-500",
    }
  );
}

function durationMs(started: string, finished: string): number {
  return new Date(finished).getTime() - new Date(started).getTime();
}

export function InsightTrace({ trace }: { trace: TraceEntry[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-xl border border-zinc-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
      >
        <div>
          <p className="text-sm font-semibold text-zinc-900">
            How we found this
          </p>
          <p className="text-xs text-zinc-500">
            LangGraph workflow · {trace.length} node
            {trace.length === 1 ? "" : "s"}
          </p>
        </div>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-zinc-500 transition-transform",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <ol className="border-t border-zinc-100">
          {trace.map((entry, i) => {
            const meta = nodeMeta(entry.node);
            const Icon = meta.icon;
            const ms = durationMs(entry.started_at, entry.finished_at);
            return (
              <li
                key={i}
                className="flex gap-3 border-b border-zinc-100 px-5 py-3 last:border-b-0"
              >
                <div
                  className={cn(
                    "mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-zinc-50",
                    meta.color,
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="text-sm font-medium text-zinc-900">
                      {i + 1}. {meta.label}
                      {entry.skipped && (
                        <span className="ml-2 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-700 ring-1 ring-amber-200">
                          skipped
                        </span>
                      )}
                    </p>
                    <p className="text-xs tabular-nums text-zinc-400">
                      {ms}ms
                      {entry.model && (
                        <span className="ml-2 text-zinc-300">
                          {entry.model}
                        </span>
                      )}
                    </p>
                  </div>
                  <p className="mt-1 text-xs text-zinc-600">{entry.summary}</p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
