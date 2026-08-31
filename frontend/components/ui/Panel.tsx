import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export function Panel({ className, children }: { className?: string; children: ReactNode }) {
  return <section className={cn("border border-rule bg-card", className)}>{children}</section>;
}

export function PanelHeader({
  title,
  right,
  count,
}: {
  title: string;
  right?: ReactNode;
  count?: number;
}) {
  return (
    <div className="flex items-center justify-between border-b border-rule px-5 py-3.5">
      <div className="text-xs font-medium uppercase tracking-wider text-fg-muted">
        {title}
        {count !== undefined && (
          <span className="figure ml-2 text-fg-faint">{count.toLocaleString("en-IN")}</span>
        )}
      </div>
      {right && <div className="text-xs text-fg-faint">{right}</div>}
    </div>
  );
}
