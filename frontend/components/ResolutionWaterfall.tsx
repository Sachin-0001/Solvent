"use client";

import { ArrowRight } from "lucide-react";
import type { ReconciliationSummary } from "@/lib/api";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatCount, formatPercent } from "@/lib/format";

interface Tier {
  key: string;
  label: string;
  count: number;
  color: string;
  detail: string;
}

function buildTiers(summary: ReconciliationSummary): Tier[] {
  const exact = summary.tier_breakdown.exact ?? 0;
  const fuzzy = summary.tier_breakdown.fuzzy ?? 0;
  const llm = summary.tier_breakdown.llm ?? 0;
  const unmatchable = summary.total_ground_truth_txns - summary.should_fully_reconcile;

  return [
    { key: "exact", label: "Exact match", count: exact, color: "var(--tier-exact)", detail: "±₹5 / 1.5% · ≤6h drift" },
    { key: "fuzzy", label: "Fuzzy match", count: fuzzy, color: "var(--tier-fuzzy)", detail: "±₹30 / 8% · ≤96h drift" },
    {
      key: "llm",
      label: "LLM reasoning",
      count: llm,
      color: "var(--tier-llm)",
      detail: llm === 0 ? "not needed - code handled it all" : "exception residual only",
    },
    {
      key: "unmatchable",
      label: "No counterpart",
      count: unmatchable,
      color: "var(--fg-faint)",
      detail: "genuinely missing by design, not a miss",
    },
  ];
}

const RING_R = 46;
const RING_SW = 13;
const RING_C = 2 * Math.PI * RING_R;

function ResolutionRing({ tiers, total, matchRate }: { tiers: Tier[]; total: number; matchRate: number }) {
  const visible = tiers.filter((t) => t.count > 0);

  return (
    <div className="relative h-[136px] w-[136px] shrink-0">
      <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
        <circle cx="60" cy="60" r={RING_R} fill="none" stroke="var(--rule)" strokeWidth={RING_SW} />
        {visible.map((t, i) => {
          const before = visible.slice(0, i).reduce((sum, x) => sum + x.count, 0);
          const dash = (t.count / total) * RING_C;
          const offset = (before / total) * RING_C;
          return (
            <circle
              key={t.key}
              cx="60"
              cy="60"
              r={RING_R}
              fill="none"
              stroke={t.color}
              strokeWidth={RING_SW}
              strokeDasharray={`${dash} ${RING_C - dash}`}
              strokeDashoffset={-offset}
            />
          );
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="figure text-2xl font-semibold text-fg">{formatPercent(matchRate)}</div>
        <div className="text-[11px] uppercase tracking-wider text-fg-faint">matched</div>
      </div>
    </div>
  );
}

export function ResolutionWaterfall({ summary }: { summary: ReconciliationSummary | null }) {
  const tiers = summary ? buildTiers(summary) : null;

  return (
    <Panel>
      <PanelHeader
        eyebrow="Reconciliation · full batch"
        title="Resolution Cascade"
        subtitle="How every transaction resolved - exact match first, then fuzzy, then LLM reasoning on the residual."
      />
      <div className="px-5 pt-1 pb-5">
        {!tiers && (
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
            <Skeleton className="h-[136px] w-[136px] shrink-0 rounded-full" />
            <div className="grid flex-1 grid-cols-1 gap-2.5 sm:grid-cols-2">
              {Array.from({ length: 4 }, (_, i) => (
                <Skeleton key={i} className="h-[58px] rounded-[var(--radius-control)]" />
              ))}
            </div>
          </div>
        )}
        {tiers && summary && (
          <>
            <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
              <ResolutionRing tiers={tiers} total={summary.total_ground_truth_txns} matchRate={summary.match_rate} />

              <div className="grid flex-1 grid-cols-1 gap-2.5 sm:grid-cols-2">
                {tiers.map((t) => {
                  const pct = (t.count / summary.total_ground_truth_txns) * 100;
                  return (
                    <div
                      key={t.key}
                      className="flex items-center gap-3 rounded-[var(--radius-control)] border border-rule bg-bg-elevated px-3 py-2.5"
                    >
                      <span
                        className="h-2.5 w-2.5 shrink-0 rounded-full"
                        style={{ backgroundColor: t.color }}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="truncate text-[13px] text-fg-muted">{t.label}</span>
                          <span className="figure text-base font-semibold text-fg">
                            {formatCount(t.count)}
                            <span className="ml-1 text-xs font-normal text-fg-faint">
                              {pct.toFixed(0)}%
                            </span>
                          </span>
                        </div>
                        <div className="mt-0.5 truncate text-xs text-fg-faint">{t.detail}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <button
              onClick={() => {
                const container = document.getElementById("dashboard-scroll");
                const target = document.getElementById("exceptions");
                if (container && target) {
                  container.scrollTo({ top: target.offsetTop - 12, behavior: "smooth" });
                }
              }}
              className="mt-4 flex w-full items-center justify-between rounded-[var(--radius-control)] border border-accent-red/25 bg-accent-red-dim px-3.5 py-2.5 text-left transition-colors hover:border-accent-red/45"
            >
              <span className="text-[13px] text-accent-red">
                <span className="figure font-semibold">{formatCount(summary.exception_count)}</span> rows
                left honest and unresolved in the Exception Ledger
              </span>
              <ArrowRight size={13} className="shrink-0 text-accent-red" />
            </button>
          </>
        )}
      </div>
    </Panel>
  );
}
