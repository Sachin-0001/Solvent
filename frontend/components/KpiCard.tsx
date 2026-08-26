type Accent = "green" | "red" | "amber" | "blue" | "neutral";

const accentClasses: Record<Accent, string> = {
  green: "text-accent-green",
  red: "text-accent-red",
  amber: "text-accent-amber",
  blue: "text-accent-blue",
  neutral: "text-fg",
};

export function KpiCard({
  label,
  value,
  suffix,
  accent = "neutral",
  sublabel,
}: {
  label: string;
  value: string;
  suffix?: string;
  accent?: Accent;
  sublabel?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 transition-colors hover:bg-card-hover">
      <div className="text-xs font-medium uppercase tracking-wider text-fg-muted">{label}</div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className={`font-mono text-3xl font-semibold tabular-nums ${accentClasses[accent]}`}>
          {value}
        </span>
        {suffix && <span className="text-sm text-fg-faint">{suffix}</span>}
      </div>
      {sublabel && <div className="mt-1 text-xs text-fg-faint">{sublabel}</div>}
    </div>
  );
}
