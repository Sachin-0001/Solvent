"use client";

import { useEffect, useState } from "react";
import { api, type ReconciliationMatch } from "@/lib/api";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { TierBadge } from "@/components/ui/Badge";
import { formatDrift, formatINRFull } from "@/lib/format";
import { cn } from "@/lib/cn";

const TIER_FILTERS = [
  { value: undefined, label: "All" },
  { value: "exact", label: "Exact" },
  { value: "fuzzy", label: "Fuzzy" },
] as const;

export function LedgerBankPairs() {
  const [tier, setTier] = useState<string | undefined>(undefined);
  const [sortDrift, setSortDrift] = useState(false);
  const [data, setData] = useState<{ total: number; items: ReconciliationMatch[] } | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .reconciliationMatches({ tier, sort: sortDrift ? "drift" : undefined, limit: 25 })
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      });
    return () => {
      cancelled = true;
    };
  }, [tier, sortDrift]);

  return (
    <Panel>
      <PanelHeader
        title="Ledger ⇄ Bank"
        count={data?.total}
        right={
          <div className="flex items-center gap-2">
            {TIER_FILTERS.map((f) => (
              <button
                key={f.label}
                onClick={() => setTier(f.value)}
                className={cn(
                  "rounded-sm border px-2 py-1 text-[11px] transition-colors",
                  tier === f.value
                    ? "border-accent-green/40 text-accent-green"
                    : "border-border-strong text-fg-muted hover:text-fg"
                )}
              >
                {f.label}
              </button>
            ))}
            <button
              onClick={() => setSortDrift((v) => !v)}
              className={cn(
                "rounded-sm border px-2 py-1 text-[11px] transition-colors",
                sortDrift
                  ? "border-accent-amber/40 text-accent-amber"
                  : "border-border-strong text-fg-muted hover:text-fg"
              )}
            >
              closest calls
            </button>
          </div>
        }
      />
      <div className="max-h-[420px] overflow-y-auto divide-y divide-rule">
        {!data && <div className="px-5 py-8 text-center text-sm text-fg-faint">loading…</div>}
        {data?.items.length === 0 && (
          <div className="px-5 py-8 text-center text-sm text-fg-faint">No matches for this filter.</div>
        )}
        {data?.items.map((m) => (
          <div key={m.id} className="grid grid-cols-1 gap-2 px-5 py-3 sm:grid-cols-[1fr_auto_1fr] sm:items-center sm:gap-4">
            <div className="min-w-0">
              <div className="figure text-sm text-fg">
                {m.ledger?.row_id ?? "—"} · {m.ledger ? formatINRFull(m.ledger.amount) : "—"}
              </div>
              {m.ledger && (
                <div className="mt-0.5 truncate text-[11px] text-fg-faint" title={m.ledger.narration ?? undefined}>
                  {m.ledger.narration}
                  {m.ledger.fee_amount ? ` · fee ${m.ledger.fee_amount.toFixed(2)}` : ""}
                  {m.ledger.tax_on_fee ? ` + gst ${m.ledger.tax_on_fee.toFixed(2)}` : ""}
                </div>
              )}
            </div>
            <div className="flex flex-col items-center gap-1 text-[11px]">
              <TierBadge tier={m.tier} />
              <span className={cn("figure", Math.abs(m.amount_diff) < 0.01 ? "text-fg-faint" : "text-accent-amber")}>
                Δ {formatDrift(m.amount_diff)}
              </span>
              <span className="text-fg-faint">{m.timestamp_diff_hours.toFixed(1)}h drift</span>
            </div>
            <div className="min-w-0 sm:text-right">
              <div className="figure text-sm text-fg">
                {m.bank ? formatINRFull(m.bank.amount) : "—"} · {m.bank?.row_id ?? "—"}
              </div>
              {m.bank && (
                <div className="mt-0.5 truncate text-[11px] text-fg-faint" title={m.bank.narration ?? undefined}>
                  {m.bank.narration}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}
