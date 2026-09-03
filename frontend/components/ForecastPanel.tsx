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
import { Skeleton } from "@/components/ui/Skeleton";
import { formatINR } from "@/lib/format";

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
    <div className="rounded-[var(--radius-control)] border border-border-strong bg-bg-elevated px-3 py-2 shadow-2xl">
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

/** Plain-English confidence sentences derived from the same validation
 * numbers the API reports (chosen_mae / mape_pct), phrased as what they mean
 * for the merchant rather than as raw model-scoring jargon. */
function confidenceLines(metrics: ForecasterMetrics | null): string[] {
  if (!metrics) return [];
  const lines: string[] = [];
  if (metrics.model_a) {
    lines.push(`Settlement timing is typically predicted within ${metrics.model_a.chosen_mae.toFixed(1)} day(s) of the actual date.`);
  }
  if (metrics.model_b_combined) {
    lines.push(`Deduction amount (fees + refunds) is typically predicted within ${(metrics.model_b_combined.mae * 100).toFixed(1)}% of the transaction value.`);
  }
  return lines;
}

export function ForecastPanel({
  days,
  referenceDate,
  modelMetrics,
}: {
  days: ForecastDay[] | null;
  referenceDate?: string;
  modelMetrics: ForecasterMetrics | null;
}) {
  const data = (days ?? []).map((d) => ({ ...d, range: [d.lower_bound, d.upper_bound] }));
  const total = (days ?? []).reduce((sum, d) => sum + d.expected_amount, 0);

  return (
    <Panel>
      <PanelHeader
        eyebrow="Trends · next 7 days"
        title="Settlement Inflow Forecast"
        subtitle="Expected net settlement arriving each day, after fees, GST, and refunds are deducted."
        right={referenceDate ? `from ${formatDate(referenceDate)}` : undefined}
      />
      <div className="px-5 pt-1">
        {days ? (
          <>
            <div className="figure text-[28px] font-semibold leading-none text-fg">
              {formatINR(total)}
            </div>
            <div className="mt-1.5 text-xs text-fg-faint">
              total expected over the window · shaded band = typical prediction range
            </div>
          </>
        ) : (
          <>
            <Skeleton className="h-7 w-36" />
            <Skeleton className="mt-2 h-3 w-64" />
          </>
        )}
      </div>
      {!days ? (
        <div className="flex h-64 items-end gap-2 px-5 pb-4 pt-2">
          {Array.from({ length: 7 }, (_, i) => (
            <Skeleton
              key={i}
              className="flex-1"
              style={{ height: `${35 + ((i * 13) % 55)}%` }}
            />
          ))}
        </div>
      ) : (
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
      )}
      {modelMetrics && confidenceLines(modelMetrics).length > 0 && (
        <div className="mt-auto flex flex-col gap-1 border-t border-rule px-5 py-3">
          {confidenceLines(modelMetrics).map((line) => (
            <div key={line} className="text-xs text-fg-faint">
              {line}
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}
