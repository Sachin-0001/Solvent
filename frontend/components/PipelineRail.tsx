import { ChevronRight } from "lucide-react";
import type { PipelineStatus } from "@/lib/api";
import { formatCount, formatHours, formatPercent } from "@/lib/format";
import { GateMark } from "@/components/ui/Badge";

interface Stage {
  name: string;
  headline: string;
  detail: string;
  gate: "passed" | "pending";
}

function buildStages(status: PipelineStatus): Stage[] {
  const modelAMae = status.forecast.model_a?.chosen_mae;
  const modelBMape = status.forecast.model_b?.chosen_mape_pct;

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
      headline: modelAMae !== undefined ? `±${formatHours(modelAMae)}` : "—",
      detail:
        modelBMape !== undefined
          ? `model A MAE ${modelAMae?.toFixed(2)}d · model B MAPE ${modelBMape.toFixed(1)}%`
          : "not yet trained",
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

export function PipelineRail({ status }: { status: PipelineStatus | null }) {
  const stages = status ? buildStages(status) : null;

  return (
    <div className="overflow-x-auto border-b border-rule">
      <div className="flex min-w-max divide-x divide-rule">
        {STAGE_NAMES.map((name, i) => {
          const stage = stages?.[i];
          return (
            <div key={name} className="flex items-stretch">
              <div className="flex w-64 flex-col items-center justify-center gap-1 px-5 py-4 text-center">
                <div className="flex items-center justify-center gap-2">
                  <span className="text-xs font-medium uppercase tracking-wider text-fg-muted">
                    {i + 1}. {name}
                  </span>
                  {stage && <GateMark gate={stage.gate} />}
                </div>
                <div className="figure text-2xl font-semibold text-fg">
                  {stage ? stage.headline : "—"}
                </div>
                <div className="text-xs text-fg-faint">
                  {stage ? stage.detail : "loading…"}
                </div>
              </div>
              {i < STAGE_NAMES.length - 1 && (
                <div className="flex items-center px-1 text-fg-faint">
                  <ChevronRight size={14} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
