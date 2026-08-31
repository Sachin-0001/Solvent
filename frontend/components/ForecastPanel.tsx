"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ForecastDay, ForecasterMetrics } from "@/lib/api";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { formatINR } from "@/lib/format";
import { cn } from "@/lib/cn";

function formatDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { payload: ForecastDay }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const day = payload[0].payload;
  return (
    <div className="border border-border-strong bg-bg-elevated px-3 py-2 shadow-xl">
      <div className="text-xs text-fg-muted">{label ? formatDate(label) : ""}</div>
      <div className="figure mt-1 text-sm font-semibold text-accent-green">
        {formatINR(day.expected_amount)}
      </div>
      <div className="figure text-xs text-fg-faint">
        {formatINR(day.lower_bound)} – {formatINR(day.upper_bound)}
      </div>
    </div>
  );
}

function ModelStat({
  name,
  metrics,
  flagged,
}: {
  name: string;
  metrics: ForecasterMetrics["model_a"];
  flagged?: boolean;
}) {
  if (!metrics) return null;
  return (
    <div className="flex items-baseline gap-1.5 text-xs">
      <span className="text-fg-muted">{name}</span>
      <span className="text-fg-faint">{metrics.chosen_model}</span>
      <span className="figure text-fg">MAE {metrics.chosen_mae}</span>
      <span className={cn("figure", flagged ? "text-accent-amber" : "text-fg")}>
        MAPE {metrics.chosen_mape_pct}%
      </span>
      <span className="text-fg-faint">
        n={metrics.n_train}/{metrics.n_test}
      </span>
    </div>
  );
}

export function ForecastPanel({
  days,
  referenceDate,
  modelMetrics,
}: {
  days: ForecastDay[];
  referenceDate?: string;
  modelMetrics: ForecasterMetrics | null;
}) {
  const data = days.map((d) => ({ ...d, range: [d.lower_bound, d.upper_bound] }));
  const total = days.reduce((sum, d) => sum + d.expected_amount, 0);

  return (
    <Panel>
      <PanelHeader
        title="7-Day Cash Forecast"
        right={
          referenceDate
            ? `demo window from ${formatDate(referenceDate)} — synthetic data, not live "today"`
            : undefined
        }
      />
      <div className="px-5 pt-4">
        <div className="figure text-2xl font-semibold text-fg">{formatINR(total)}</div>
        <div className="mt-0.5 text-xs text-fg-faint">
          expected net settlement · dashed lines = ± held-out MAE
        </div>
      </div>
      <div className="h-64 px-3 pt-2 pb-1">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
            <defs>
              <linearGradient id="expectedFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent-green)" stopOpacity={0.25} />
                <stop offset="100%" stopColor="var(--accent-green)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--rule)" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              tick={{ fill: "var(--fg-muted)", fontSize: 12 }}
              axisLine={{ stroke: "var(--rule-strong)" }}
              tickLine={false}
            />
            <YAxis
              tickFormatter={formatINR}
              tick={{ fill: "var(--fg-muted)", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              width={56}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area dataKey="range" stroke="none" fill="var(--accent-blue)" fillOpacity={0.16} isAnimationActive={false} />
            <Line
              dataKey="upper_bound"
              stroke="var(--accent-blue)"
              strokeWidth={1}
              strokeDasharray="3 3"
              strokeOpacity={0.6}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              dataKey="lower_bound"
              stroke="var(--accent-blue)"
              strokeWidth={1}
              strokeDasharray="3 3"
              strokeOpacity={0.6}
              dot={false}
              isAnimationActive={false}
            />
            <Area
              dataKey="expected_amount"
              stroke="var(--accent-green)"
              strokeWidth={2}
              fill="url(#expectedFill)"
              isAnimationActive={false}
            />
            <Line
              dataKey="expected_amount"
              stroke="var(--accent-green)"
              strokeWidth={2}
              dot={{ r: 3, fill: "var(--bg)", stroke: "var(--accent-green)", strokeWidth: 2 }}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {modelMetrics && (
        <div className="flex flex-col gap-1.5 border-t border-rule px-5 py-3">
          <ModelStat name="Model A · days_to_settle" metrics={modelMetrics.model_a} />
          <ModelStat name="Model B · deduction_pct" metrics={modelMetrics.model_b} flagged />
        </div>
      )}
    </Panel>
  );
}
