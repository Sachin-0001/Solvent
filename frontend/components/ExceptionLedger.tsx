"use client";

import { useMemo, useState } from "react";
import type { ReconciliationException } from "@/lib/api";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { Badge, SideMarker } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";

const REASON_META: Record<string, { label: string; tone: "red" | "amber" | "neutral" }> = {
  missing_counterpart: { label: "Missing counterpart", tone: "red" },
  likely_duplicate: { label: "Likely duplicate", tone: "amber" },
  unexplained: { label: "Unexplained", tone: "neutral" },
};

export function ExceptionLedger({ exceptions }: { exceptions: ReconciliationException[] }) {
  const [reasonFilter, setReasonFilter] = useState<string | null>(null);

  const reasonCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of exceptions) counts[e.reason] = (counts[e.reason] ?? 0) + 1;
    return counts;
  }, [exceptions]);

  const sideCounts = useMemo(() => {
    const counts: Record<string, number> = { ledger: 0, bank: 0 };
    for (const e of exceptions) counts[e.side] = (counts[e.side] ?? 0) + 1;
    return counts;
  }, [exceptions]);

  const filtered = reasonFilter ? exceptions.filter((e) => e.reason === reasonFilter) : exceptions;

  return (
    <Panel>
      <PanelHeader
        title="Exception Ledger"
        count={exceptions.length}
        right={`${sideCounts.ledger} ledger · ${sideCounts.bank} bank`}
      />
      <div className="flex flex-wrap gap-2 border-b border-rule px-5 py-3">
        <button
          onClick={() => setReasonFilter(null)}
          className={cn(
            "rounded-sm border px-2 py-1 text-[11px] transition-colors",
            reasonFilter === null
              ? "border-accent-green/40 text-accent-green"
              : "border-border-strong text-fg-muted hover:text-fg"
          )}
        >
          All ({exceptions.length})
        </button>
        {Object.entries(reasonCounts).map(([reason, count]) => {
          const meta = REASON_META[reason] ?? { label: reason, tone: "neutral" as const };
          return (
            <button key={reason} onClick={() => setReasonFilter(reason)}>
              <Badge tone={reasonFilter === reason ? meta.tone : "neutral"}>
                {meta.label} ({count})
              </Badge>
            </button>
          );
        })}
      </div>
      <div className="max-h-[420px] overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-fg-faint">
            No exceptions — everything reconciled cleanly.
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-card">
              <tr className="text-[11px] uppercase tracking-wider text-fg-faint">
                <th className="px-5 py-2 font-medium">Side</th>
                <th className="px-2 py-2 font-medium">Row</th>
                <th className="px-2 py-2 font-medium">Order</th>
                <th className="px-2 py-2 font-medium">Reason</th>
                <th className="px-5 py-2 font-medium">Explanation</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => {
                const meta = REASON_META[e.reason] ?? { label: e.reason, tone: "neutral" as const };
                return (
                  <tr key={e.id} className="border-t border-rule hover:bg-card-hover">
                    <td className="px-5 py-2.5">
                      <SideMarker side={e.side} />
                    </td>
                    <td className="figure px-2 py-2.5 text-xs text-fg">{e.row_id}</td>
                    <td className="figure px-2 py-2.5 text-xs text-fg-muted">{e.order_id ?? "—"}</td>
                    <td className="px-2 py-2.5">
                      <Badge tone={meta.tone}>{meta.label}</Badge>
                    </td>
                    <td className="px-5 py-2.5 text-xs text-fg-muted">{e.explanation}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </Panel>
  );
}
