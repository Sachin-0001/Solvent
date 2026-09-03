import type { CashPosition, PipelineStatus } from "@/lib/api";
import { formatCount, formatINR, formatPercent } from "@/lib/format";
import { GateMark } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";

interface Stage {
  name: string;
  headline: string;
  detail: string;
  gate: "passed" | "pending";
}

function buildStages(status: PipelineStatus, cashPosition: CashPosition | null): Stage[] {
  return [
    {
      name: "Ingest",
      headline: `${formatCount(status.ingest.total_transactions)} txns`,
      detail: `${status.ingest.ledger_rows} ledger · ${status.ingest.bank_rows} bank rows`,
      gate: status.ingest.gate,
    },
    {
      name: "Reconcile",
      headline: formatPercent(status.reconcile.match_rate),
      detail: `${status.reconcile.reported_matches}/${status.reconcile.total_ground_truth_txns} matched · ${status.reconcile.exception_count} exceptions`,
      gate: status.reconcile.gate,
    },
    {
      name: "Classify",
      headline: `${formatCount(status.classify.total)} classified`,
      detail: `${status.classify.resolved_by_rules} by rule · ${status.classify.resolved_by_llm} by LLM`,
      gate: status.classify.gate,
    },
    {
      name: "Forecast",
      headline: cashPosition ? formatINR(cashPosition.projected_cash) : "-",
      detail: cashPosition
        ? `projected cash for ${cashPosition.forecast_date ?? "tomorrow"}`
        : "not yet available",
      gate: status.forecast.gate,
    },
    {
      name: "Ask",
      headline: `${formatCount(status.qa.indexed_records)} indexed`,
      detail: "semantic retrieval, brute-force cosine",
      gate: status.qa.gate,
    },
  ];
}

const STAGE_NAMES = ["Ingest", "Reconcile", "Classify", "Forecast", "Ask"];

export function PipelineRail({
  status,
  cashPosition,
}: {
  status: PipelineStatus | null;
  cashPosition: CashPosition | null;
}) {
  const stages = status ? buildStages(status, cashPosition) : null;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {STAGE_NAMES.map((name, i) => {
        const stage = stages?.[i];
        return (
          <div
            key={name}
            className="rounded-[var(--radius-card)] border border-rule bg-card px-4 py-3.5 transition-colors hover:border-rule-strong"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] font-medium uppercase tracking-wider text-fg-faint">
                {name}
              </span>
              {stage ? <GateMark gate={stage.gate} /> : <Skeleton className="h-3.5 w-3.5 rounded-full" />}
            </div>
            {stage ? (
              <div className="figure mt-2 truncate text-[22px] font-semibold leading-none text-fg">
                {stage.headline}
              </div>
            ) : (
              <Skeleton className="mt-2 h-[22px] w-20" />
            )}
            {stage ? (
              <div className="mt-1.5 truncate text-xs text-fg-muted">{stage.detail}</div>
            ) : (
              <Skeleton className="mt-1.5 h-3 w-28" />
            )}
          </div>
        );
      })}
    </div>
  );
}
