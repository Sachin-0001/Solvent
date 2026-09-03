"use client";

import { useState } from "react";
import { api, type TaxClassificationRecord, type TaxSummary } from "@/lib/api";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/cn";

const CATEGORY_META: Record<string, { label: string; color: string }> = {
  taxable_sale: { label: "Taxable Sale", color: "var(--accent-blue)" },
  gst_on_fee: { label: "GST on Fee", color: "var(--accent-green)" },
  exempt: { label: "Exempt", color: "var(--accent-amber)" },
  refund_credit_note: { label: "Refund / Credit Note", color: "var(--accent-red)" },
  unresolved: { label: "Unresolved", color: "var(--fg-faint)" },
};

export function TaxLedger({ summary }: { summary: TaxSummary | null }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [rows, setRows] = useState<TaxClassificationRecord[] | null>(null);
  const [loading, setLoading] = useState(false);

  async function toggle(category: string) {
    if (expanded === category) {
      setExpanded(null);
      return;
    }
    setExpanded(category);
    setLoading(true);
    try {
      const res = await api.taxClassifications({ category, limit: 8 });
      setRows(res.items);
    } catch {
      setRows(null);
    } finally {
      setLoading(false);
    }
  }

  const entries = summary
    ? Object.entries(summary.category_breakdown).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <Panel>
      <PanelHeader
        eyebrow="GST treatment · full batch"
        title="Tax Classification"
        subtitle="How each line was classified for GST. Click a category to see the per-transaction reasoning."
        count={summary?.total}
        right={
          summary
            ? `${summary.resolved_by_rules} by rule · ${summary.resolved_by_llm} by LLM`
            : undefined
        }
      />
      <div className="flex flex-1 flex-col justify-center space-y-1 px-5 pt-1 pb-4">
        {!summary &&
          Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="py-2">
              <div className="mb-1 flex items-center justify-between">
                <Skeleton className="h-3.5 w-24" />
                <Skeleton className="h-3.5 w-10" />
              </div>
              <Skeleton className="h-1.5 w-full" />
            </div>
          ))}
        {entries.map(([category, count]) => {
          const meta = CATEGORY_META[category] ?? { label: category, color: "var(--fg-muted)" };
          const pct = summary ? (count / summary.total) * 100 : 0;
          const isOpen = expanded === category;
          return (
            <div key={category}>
              <button
                onClick={() => toggle(category)}
                className="w-full py-2 text-left"
              >
                <div className="mb-1 flex items-center justify-between text-[13px]">
                  <span className={cn("text-fg-muted", isOpen && "text-fg")}>{meta.label}</span>
                  <span className="figure text-fg">
                    {count} <span className="text-fg-faint">({pct.toFixed(0)}%)</span>
                  </span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-sm bg-white/5">
                  <div
                    className="h-full rounded-sm transition-all duration-700"
                    style={{ width: `${pct}%`, backgroundColor: meta.color }}
                  />
                </div>
              </button>
              {isOpen && (
                <div className="mb-2 space-y-1.5 border-l border-rule pl-3">
                  {loading &&
                    Array.from({ length: 3 }, (_, i) => (
                      <Skeleton key={i} className="h-3.5 w-full" />
                    ))}
                  {!loading &&
                    rows?.map((r) => (
                      <div key={r.txn_id} className="text-[13px]">
                        <span className="figure text-fg-muted">{r.txn_id}</span>{" "}
                        <span className="text-fg-faint">{r.reasoning}</span>
                      </div>
                    ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}
