import type { TaxSummary } from "@/lib/api";

const CATEGORY_META: Record<string, { label: string; color: string }> = {
  taxable_sale: { label: "Taxable Sale", color: "#5b8def" },
  gst_on_fee: { label: "GST on Fee", color: "#22d3a8" },
  exempt: { label: "Exempt", color: "#f5b942" },
  refund_credit_note: { label: "Refund / Credit Note", color: "#f5576c" },
  unresolved: { label: "Unresolved", color: "#565e6c" },
};

export function TaxBreakdown({ summary }: { summary: TaxSummary }) {
  const entries = Object.entries(summary.category_breakdown).sort((a, b) => b[1] - a[1]);

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-baseline justify-between">
        <div className="text-xs font-medium uppercase tracking-wider text-fg-muted">
          Tax Classification
        </div>
        <div className="text-[11px] text-fg-faint">
          {summary.resolved_by_rules} by rule · {summary.resolved_by_llm} by LLM
        </div>
      </div>
      <div className="mt-4 space-y-3">
        {entries.map(([category, count]) => {
          const meta = CATEGORY_META[category] ?? { label: category, color: "#8b93a1" };
          const pct = (count / summary.total) * 100;
          return (
            <div key={category}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="text-fg-muted">{meta.label}</span>
                <span className="font-mono text-fg">
                  {count} <span className="text-fg-faint">({pct.toFixed(0)}%)</span>
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/5">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${pct}%`, backgroundColor: meta.color }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
