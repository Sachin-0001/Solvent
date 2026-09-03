"use client";

import { Database, RefreshCw } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

/** Pill control matching the reference toolbar's bordered chips. */
function Chip({
  children,
  icon: Icon,
  onClick,
}: {
  children: React.ReactNode;
  icon?: LucideIcon;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1.5 rounded-[var(--radius-control)] border border-border-strong px-2.5 py-1.5 text-xs text-fg-muted transition-colors hover:border-rule-strong hover:bg-card-hover hover:text-fg"
    >
      {Icon && <Icon size={12} className="text-fg-faint" />}
      {children}
    </button>
  );
}

function relativeTime(date: Date | null): string {
  if (!date) return "never";
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours} hour${hours === 1 ? "" : "s"} ago`;
}

export function DashboardHeader({
  lastUpdated,
  healthy,
  transactionCount,
  onSwitchSource,
}: {
  lastUpdated: Date | null;
  healthy: boolean | null;
  transactionCount: number | null;
  onSwitchSource: () => void;
}) {
  return (
    <div id="top" className="border-b border-rule px-7 pt-5 pb-4">
      {/* Breadcrumb */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-1.5 text-xs text-fg-faint">
          <span className="transition-colors hover:text-fg-muted">Solvent</span>
          <span>/</span>
          <span className="transition-colors hover:text-fg-muted">Finance controller</span>
          <span>/</span>
          <span className="text-fg-muted">Dashboards</span>
        </div>

        <div
          className={cn(
            "flex items-center gap-1.5 rounded-[var(--radius-control)] border px-2 py-1 text-xs",
            healthy === false
              ? "border-accent-red/30 bg-accent-red-dim text-accent-red"
              : "border-accent-green/25 bg-accent-green-dim text-accent-green"
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              healthy === false ? "bg-accent-red" : "pulse-dot bg-accent-green"
            )}
          />
          {healthy === false ? "Offline" : "Live"}
        </div>
      </div>

      {/* Title */}
      <h1 className="mt-3 text-[22px] font-semibold tracking-tight text-fg">
        Settlement &amp; Cash Position
      </h1>

      {/* Description */}
      <p className="mt-1 text-[13px] text-fg-muted">
        Reconciliation health, GST treatment, and forward cash position across{" "}
        {transactionCount !== null ? transactionCount.toLocaleString("en-IN") : "-"} transactions.
      </p>

      {/* Toolbar - only controls that actually do something. */}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Chip icon={Database} onClick={onSwitchSource}>
          Sample data · switch source
        </Chip>
        <div className="ml-auto flex items-center gap-1.5 text-xs text-fg-faint">
          <RefreshCw size={11} />
          Last updated {relativeTime(lastUpdated)}
        </div>
      </div>
    </div>
  );
}
