"use client";

import { useState } from "react";
import type { CashPosition, GmvForecast } from "@/lib/api";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatINR } from "@/lib/format";
import { cn } from "@/lib/cn";

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}

function MethodBadge({ method }: { method: string }) {
  return (
    <Badge tone={method === "linear_regression" ? "blue" : "neutral"}>
      {method === "linear_regression" ? "predicted" : "based on yesterday"}
    </Badge>
  );
}

function FlowRow({
  label,
  value,
  sign,
  method,
}: {
  label: string;
  value: number;
  sign: "+" | "-";
  method: string;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-2">
        <span className="text-sm text-fg-muted">{label}</span>
        <MethodBadge method={method} />
      </div>
      <span
        className={cn(
          "figure text-sm font-medium",
          sign === "+" ? "text-accent-green" : "text-accent-red"
        )}
      >
        {sign} {formatINR(value)}
      </span>
    </div>
  );
}

export function CashPositionPanel({
  cashPosition,
  gmvForecast,
  onCurrentCashChange,
}: {
  cashPosition: CashPosition | null;
  gmvForecast: GmvForecast | null;
  onCurrentCashChange: (value: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  if (!cashPosition) {
    return (
      <Panel>
        <PanelHeader eyebrow="Cash position · next day" title="Projected Cash" />
        <div className="px-5 pt-1 pb-4">
          <Skeleton className="h-[32px] w-40" />
          <Skeleton className="mt-2.5 h-4 w-48" />
          <div className="mt-4 divide-y divide-rule border-t border-rule">
            {Array.from({ length: 3 }, (_, i) => (
              <div key={i} className="flex items-center justify-between py-2">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-20" />
              </div>
            ))}
          </div>
        </div>
      </Panel>
    );
  }

  const netUp = cashPosition.expected_net_cash_flow >= 0;

  return (
    <Panel>
      <PanelHeader
        eyebrow="Cash position · next day"
        title="Projected Cash"
        subtitle="Where your balance lands tomorrow once expected settlements arrive and refunds are paid out."
        right={
          cashPosition.forecast_date
            ? `for ${formatDate(cashPosition.forecast_date)}`
            : undefined
        }
      />

      <div className="px-5 pt-1 pb-4">
        {/* Hero figure - projected cash */}
        <div className="figure text-[32px] font-semibold leading-none text-fg">
          {formatINR(cashPosition.projected_cash)}
        </div>
        <div className="mt-1.5 flex items-center gap-2 text-xs">
          <span
            className={cn(
              "figure rounded-[var(--radius-control)] px-1.5 py-0.5 font-medium",
              netUp
                ? "bg-accent-green-dim text-accent-green"
                : "bg-accent-red-dim text-accent-red"
            )}
          >
            {netUp ? "+" : ""}
            {formatINR(cashPosition.expected_net_cash_flow)}
          </span>
          <span className="text-fg-faint">net movement vs. today</span>
        </div>

        {/* Breakdown */}
        <div className="mt-4 divide-y divide-rule border-t border-rule">
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-2">
              <span className="text-sm text-fg-muted">Current cash</span>
              <Badge tone="neutral">configured</Badge>
            </div>
            {editing ? (
              <form
                className="flex items-center gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  const parsed = Number(draft);
                  if (!Number.isNaN(parsed) && parsed >= 0) onCurrentCashChange(parsed);
                  setEditing(false);
                }}
              >
                <input
                  autoFocus
                  className="figure w-32 rounded-[var(--radius-control)] border border-border-strong bg-bg px-2 py-1 text-sm text-fg outline-none focus:border-accent"
                  defaultValue={cashPosition.current_cash}
                  onChange={(e) => setDraft(e.target.value)}
                  type="number"
                  min={0}
                />
                <button type="submit" className="text-xs text-accent hover:text-accent-hover">
                  save
                </button>
              </form>
            ) : (
              <button
                className="figure text-sm font-medium text-fg transition-colors hover:text-accent"
                onClick={() => {
                  setDraft(String(cashPosition.current_cash));
                  setEditing(true);
                }}
                title="Configured input, not a live account balance - click to change"
              >
                {formatINR(cashPosition.current_cash)}
              </button>
            )}
          </div>

          <FlowRow
            label="Expected settlement"
            value={cashPosition.expected_settlement}
            sign="+"
            method={cashPosition.forecast_method.settlement.method}
          />
          <FlowRow
            label="Expected refunds"
            value={cashPosition.expected_refunds}
            sign="-"
            method={cashPosition.forecast_method.refunds.method}
          />
        </div>
      </div>

      <div className="mt-auto flex items-center justify-between border-t border-rule px-5 py-3 text-xs text-fg-faint">
        <span>Tomorrow&apos;s expected sales volume</span>
        {gmvForecast ? (
          <span className="figure text-fg-muted">{formatINR(gmvForecast.value)}</span>
        ) : (
          <span>-</span>
        )}
      </div>
    </Panel>
  );
}
