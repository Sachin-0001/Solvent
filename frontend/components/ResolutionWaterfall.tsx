import type { ReconciliationSummary } from "@/lib/api";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { formatCount, formatPercent } from "@/lib/format";

interface Rung {
  label: string;
  count: number;
  color: string;
  note: string;
}

function buildRungs(summary: ReconciliationSummary): Rung[] {
  const exact = summary.tier_breakdown.exact ?? 0;
  const fuzzy = summary.tier_breakdown.fuzzy ?? 0;
  const llm = summary.tier_breakdown.llm ?? 0;

  return [
    {
      label: "Ground truth",
      count: summary.total_ground_truth_txns,
      color: "var(--fg-faint)",
      note: "transactions in the validation set",
    },
    {
      label: "Exact match",
      count: exact,
      color: "var(--tier-exact)",
      note: "±₹5 / 1.5% · ≤6h drift",
    },
    {
      label: "Fuzzy match",
      count: fuzzy,
      color: "var(--tier-fuzzy)",
      note: "±₹30 / 8% · ≤96h drift",
    },
    {
      label: "LLM reasoning",
      count: llm,
      color: "var(--tier-llm)",
      note: llm === 0 ? "not needed — code handled the full set" : "exception residual only",
    },
    {
      label: "Exceptions",
      count: summary.exception_count,
      color: "var(--accent-red)",
      note: "honest, unresolved, reasoned",
    },
  ];
}

export function ResolutionWaterfall({ summary }: { summary: ReconciliationSummary | null }) {
  const rungs = summary ? buildRungs(summary) : null;
  const max = rungs ? Math.max(...rungs.map((r) => r.count), 1) : 1;

  return (
    <Panel>
      <PanelHeader
        title="Resolution Waterfall"
        right={summary ? `precision ${formatPercent(summary.precision)} · recall ${formatPercent(summary.recall)}` : undefined}
      />
      <div className="space-y-3 px-5 py-4">
        {(rungs ?? []).map((rung) => (
          <div key={rung.label}>
            <div className="mb-1 flex items-baseline justify-between text-xs">
              <span className="text-fg-muted">{rung.label}</span>
              <span className="figure text-fg">
                {formatCount(rung.count)}{" "}
                <span className="text-fg-faint">{rung.note}</span>
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-sm bg-white/5">
              <div
                className="h-full rounded-sm transition-all duration-700"
                style={{ width: `${(rung.count / max) * 100}%`, backgroundColor: rung.color }}
              />
            </div>
          </div>
        ))}
        {!rungs && <div className="text-xs text-fg-faint">loading…</div>}
      </div>
    </Panel>
  );
}
