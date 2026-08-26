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
import type { ForecastDay } from "@/lib/api";

function formatDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}

function formatINR(value: number): string {
  if (value >= 1000) return `₹${(value / 1000).toFixed(1)}k`;
  return `₹${value.toFixed(0)}`;
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
    <div className="rounded-lg border border-border-strong bg-bg-elevated px-3 py-2 shadow-xl">
      <div className="text-xs text-fg-muted">{label ? formatDate(label) : ""}</div>
      <div className="mt-1 font-mono text-sm font-semibold text-accent-green">
        {formatINR(day.expected_amount)}
      </div>
      <div className="font-mono text-[11px] text-fg-faint">
        {formatINR(day.lower_bound)} – {formatINR(day.upper_bound)}
      </div>
    </div>
  );
}

export function ForecastChart({
  days,
  referenceDate,
}: {
  days: ForecastDay[];
  referenceDate?: string;
}) {
  const data = days.map((d) => ({ ...d, range: [d.lower_bound, d.upper_bound] }));
  const total = days.reduce((sum, d) => sum + d.expected_amount, 0);

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-baseline justify-between">
        <div>
          <div className="text-xs font-medium uppercase tracking-wider text-fg-muted">
            7-Day Cash Forecast
          </div>
          <div className="mt-1 font-mono text-2xl font-semibold text-fg">{formatINR(total)}</div>
          {referenceDate && (
            <div className="mt-0.5 text-[11px] text-fg-faint">
              demo window starting {formatDate(referenceDate)} — synthetic data, not live &quot;today&quot;
            </div>
          )}
        </div>
        <div className="text-right text-[11px] text-fg-faint">
          expected net settlement
          <br />
          dashed lines = confidence band
        </div>
      </div>
      <div className="mt-4 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
            <defs>
              <linearGradient id="expectedFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#22d3a8" stopOpacity={0.25} />
                <stop offset="100%" stopColor="#22d3a8" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              tick={{ fill: "#8b93a1", fontSize: 11 }}
              axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
              tickLine={false}
            />
            <YAxis
              tickFormatter={formatINR}
              tick={{ fill: "#8b93a1", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={56}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              dataKey="range"
              stroke="none"
              fill="#5b8def"
              fillOpacity={0.16}
              isAnimationActive={false}
            />
            <Line
              dataKey="upper_bound"
              stroke="#5b8def"
              strokeWidth={1}
              strokeDasharray="3 3"
              strokeOpacity={0.6}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              dataKey="lower_bound"
              stroke="#5b8def"
              strokeWidth={1}
              strokeDasharray="3 3"
              strokeOpacity={0.6}
              dot={false}
              isAnimationActive={false}
            />
            <Area
              dataKey="expected_amount"
              stroke="#22d3a8"
              strokeWidth={2}
              fill="url(#expectedFill)"
              isAnimationActive={false}
            />
            <Line
              dataKey="expected_amount"
              stroke="#22d3a8"
              strokeWidth={2}
              dot={{ r: 3, fill: "#0a0e14", stroke: "#22d3a8", strokeWidth: 2 }}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
