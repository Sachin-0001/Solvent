import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export function Panel({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <section
      className={cn(
        "flex h-full flex-col overflow-hidden rounded-[var(--radius-card)] border border-rule bg-card shadow-[0_1px_2px_rgba(0,0,0,0.4)] transition-colors hover:border-rule-strong",
        className
      )}
    >
      {children}
    </section>
  );
}

/**
 * Card head matching the reference insight-card anatomy:
 *   eyebrow (small caps, e.g. "TRENDS · LAST 30 DAYS")  ·  Show details  ⋯
 *   Title
 *   one-line subtitle explaining what the metric is
 */
export function PanelHeader({
  title,
  eyebrow,
  subtitle,
  right,
  count,
}: {
  title: string;
  eyebrow?: string;
  subtitle?: ReactNode;
  right?: ReactNode;
  count?: number;
}) {
  return (
    <div className="px-5 pt-4 pb-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {eyebrow && (
            <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-fg-faint">
              {eyebrow}
            </div>
          )}
          <div className="flex items-baseline gap-2">
            <h2 className="text-[15px] font-semibold tracking-tight text-fg">{title}</h2>
            {count !== undefined && (
              <span className="figure text-xs text-fg-faint">{count.toLocaleString("en-IN")}</span>
            )}
          </div>
        </div>

        {right && <div className="shrink-0 text-xs text-fg-faint">{right}</div>}
      </div>

      {subtitle && <p className="mt-1 text-xs leading-relaxed text-fg-muted">{subtitle}</p>}
    </div>
  );
}
