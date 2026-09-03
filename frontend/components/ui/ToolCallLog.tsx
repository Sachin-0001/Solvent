"use client";

import { useState } from "react";
import { Check, ChevronRight, X, Wrench } from "lucide-react";
import type { ToolCallTrace } from "@/lib/api";
import { cn } from "@/lib/cn";

/** search_payments -> "Search payments" */
function humanizeToolName(name: string): string {
  const s = name.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function formatArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args).filter(([, v]) => v !== undefined && v !== null);
  if (entries.length === 0) return "no filters";
  return entries.map(([k, v]) => `${k.replace(/_/g, " ")}: ${JSON.stringify(v)}`).join(" · ");
}

/**
 * The agent's tool chain as a stepped timeline. Collapsed by default to a
 * one-line summary so answers stay readable, expandable for the full audit
 * trail - which is the point of showing it at all in a finance tool.
 */
export function ToolCallLog({ trace }: { trace: ToolCallTrace[] }) {
  const [open, setOpen] = useState(false);
  if (trace.length === 0) return null;

  const failed = trace.filter((t) => t.status === "error").length;
  const totalMs = trace.reduce((sum, t) => sum + t.duration_ms, 0);

  return (
    <div className="mb-2 overflow-hidden rounded-[var(--radius-control)] border border-rule bg-bg-elevated">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left transition-colors hover:bg-card-hover"
      >
        <Wrench size={11} className="shrink-0 text-fg-faint" />
        <span className="text-[11px] text-fg-muted">
          {trace.length} tool{trace.length === 1 ? "" : "s"} used
          {failed > 0 && <span className="text-accent-red"> · {failed} failed</span>}
        </span>
        <span className="figure ml-auto text-[11px] text-fg-faint">{totalMs}ms</span>
        <ChevronRight
          size={11}
          className={cn("shrink-0 text-fg-faint transition-transform", open && "rotate-90")}
        />
      </button>

      {open && (
        <div className="border-t border-rule px-2.5 py-2">
          <div className="flex flex-col gap-2">
            {trace.map((t, i) => {
              const ok = t.status === "success";
              return (
                <div key={i} className="flex gap-2">
                  {/* Step rail */}
                  <div className="flex flex-col items-center">
                    <span
                      className={cn(
                        "flex h-4 w-4 shrink-0 items-center justify-center rounded-full",
                        ok ? "bg-accent-green-dim" : "bg-accent-red-dim"
                      )}
                    >
                      {ok ? (
                        <Check size={9} className="text-accent-green" />
                      ) : (
                        <X size={9} className="text-accent-red" />
                      )}
                    </span>
                    {i < trace.length - 1 && <span className="mt-0.5 w-px flex-1 bg-rule" />}
                  </div>

                  <div className="min-w-0 flex-1 pb-0.5">
                    <div className="flex items-baseline gap-1.5">
                      <span
                        className={cn(
                          "text-[11px] font-medium",
                          ok ? "text-fg" : "text-accent-red"
                        )}
                      >
                        {humanizeToolName(t.name)}
                      </span>
                      <span className="figure text-[10px] text-fg-faint">{t.duration_ms}ms</span>
                    </div>
                    <div className="figure mt-0.5 truncate text-[10px] text-fg-faint">
                      {formatArgs(t.arguments)}
                    </div>
                    <div
                      className={cn(
                        "mt-0.5 text-[10px]",
                        ok ? "text-fg-muted" : "text-accent-red/80"
                      )}
                    >
                      → {t.result_summary}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
