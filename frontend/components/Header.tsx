import { Database, Sparkles } from "lucide-react";
import { cn } from "@/lib/cn";

const NAV_LINKS = [
  { label: "Reconcile", href: "#reconciliation" },
  { label: "Ledger ⇄ Bank", href: "#ledger-bank" },
  { label: "Exceptions", href: "#exceptions" },
  { label: "Forecast", href: "#forecast" },
  { label: "Tax", href: "#tax" },
];

export function Header({
  lastUpdated,
  healthy,
  sourceCounts,
  onOpenAsk,
}: {
  lastUpdated: Date | null;
  healthy: boolean | null;
  sourceCounts: Record<string, number> | null;
  onOpenAsk: () => void;
}) {
  const real = sourceCounts?.razorpay_real ?? 0;
  const synthetic = sourceCounts?.synthetic ?? 0;

  return (
    <header className="sticky top-0 z-20 border-b border-rule bg-bg/95 backdrop-blur">
      <div className="h-[2px] bg-gradient-to-r from-accent-green via-accent-blue to-transparent" />
      <div className="flex items-center justify-between gap-4 px-6 py-3.5">
        <div className="flex items-center gap-3">
          <div className="relative flex h-8 w-8 items-center justify-center border border-accent-green/25 bg-accent-green-dim font-mono text-sm font-bold text-accent-green transition-colors hover:border-accent-green/50">
            S
            <span className="pulse-dot absolute -top-1 -right-1 h-1.5 w-1.5 rounded-full bg-accent-green" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight text-fg">Solvent</div>
            <div className="text-xs tracking-wide text-fg-faint">AI Finance-Controller Pipeline</div>
          </div>
          {sourceCounts && (
            <span className="figure ml-2 hidden items-center gap-1.5 rounded-sm border border-dashed border-border-strong px-2 py-1 text-xs text-fg-muted sm:inline-flex">
              <Database size={11} className="text-fg-faint" />
              {real} live Razorpay · {synthetic} synthetic
            </span>
          )}
        </div>

        <nav className="hidden flex-1 items-center justify-center gap-5 lg:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-xs font-medium uppercase tracking-wider text-fg-muted transition-colors hover:text-accent-green"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <button
            onClick={onOpenAsk}
            className="flex items-center gap-2 border border-accent-green/30 bg-accent-green-dim px-3 py-1.5 text-xs font-medium text-accent-green transition-colors hover:border-accent-green/60 hover:bg-accent-green/15"
          >
            <Sparkles size={12} />
            Ask AI
            <span className="figure hidden rounded-sm border border-accent-green/30 px-1 text-[11px] text-accent-green/80 md:inline-block">
              ⌘K
            </span>
          </button>

          <div className="hidden items-center gap-2 rounded-sm border border-border-strong px-2.5 py-1.5 text-xs text-fg-muted sm:flex">
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
      </div>
    </header>
  );
}
