import { cn } from "@/lib/cn";

export function Header({
  lastUpdated,
  healthy,
  sourceCounts,
}: {
  lastUpdated: Date | null;
  healthy: boolean | null;
  sourceCounts: Record<string, number> | null;
}) {
  const real = sourceCounts?.razorpay_real ?? 0;
  const synthetic = sourceCounts?.synthetic ?? 0;

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between border-b border-rule bg-bg/95 px-6 py-3.5 backdrop-blur">
      <div className="flex items-center gap-3">
        <div className="flex h-7 w-7 items-center justify-center border border-accent-green/25 bg-accent-green-dim font-mono text-xs font-bold text-accent-green">
          S
        </div>
        <div>
          <div className="text-sm font-semibold tracking-tight text-fg">Solvent</div>
          <div className="text-[10px] text-fg-faint">AI Finance-Controller Pipeline</div>
        </div>
        {sourceCounts && (
          <span className="figure ml-2 hidden rounded-sm border border-border-strong px-2 py-1 text-[10px] text-fg-muted sm:inline-block">
            {real} live Razorpay · {synthetic} synthetic
          </span>
        )}
      </div>
      <div className="flex items-center gap-4 text-xs text-fg-muted">
        <span className="hidden rounded-sm border border-border-strong px-1.5 py-0.5 font-mono text-[10px] text-fg-faint md:inline-block">
          ⌘K ask
        </span>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              healthy === false ? "bg-accent-red" : "pulse-dot bg-accent-green"
            )}
          />
          <span className={healthy === false ? "text-accent-red" : undefined}>
            {healthy === false ? "Offline" : "Live"}
          </span>
          {lastUpdated && (
            <span className="figure text-fg-faint">
              · {lastUpdated.toLocaleTimeString("en-IN", { hour12: false })}
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
