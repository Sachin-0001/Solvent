export function Header({ lastUpdated }: { lastUpdated: Date | null }) {
  return (
    <header className="flex items-center justify-between border-b border-border px-8 py-5">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-green/10 font-mono text-sm font-bold text-accent-green">
          S
        </div>
        <div>
          <div className="text-sm font-semibold tracking-tight text-fg">Solvent</div>
          <div className="text-[11px] text-fg-faint">Settlement Intelligence</div>
        </div>
      </div>
      <div className="flex items-center gap-2 text-xs text-fg-muted">
        <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent-green" />
        <span>Live</span>
        {lastUpdated && (
          <span className="font-mono text-fg-faint">
            · updated {lastUpdated.toLocaleTimeString("en-IN", { hour12: false })}
          </span>
        )}
      </div>
    </header>
  );
}
