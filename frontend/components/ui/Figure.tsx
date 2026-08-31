import { cn } from "@/lib/cn";

type Accent = "green" | "red" | "amber" | "blue" | "neutral";

const accentClasses: Record<Accent, string> = {
  green: "text-accent-green",
  red: "text-accent-red",
  amber: "text-accent-amber",
  blue: "text-accent-blue",
  neutral: "text-fg",
};

export function Figure({
  label,
  value,
  suffix,
  accent = "neutral",
  sublabel,
  size = "lg",
}: {
  label: string;
  value: string;
  suffix?: string;
  accent?: Accent;
  sublabel?: string;
  size?: "lg" | "md";
}) {
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-wider text-fg-muted">
        {label}
      </div>
      <div className="mt-1.5 flex items-baseline gap-1">
        <span
          className={cn(
            "figure font-semibold",
            size === "lg" ? "text-3xl" : "text-xl",
            accentClasses[accent]
          )}
        >
          {value}
        </span>
        {suffix && <span className="text-sm text-fg-faint">{suffix}</span>}
      </div>
      {sublabel && <div className="mt-1 text-xs text-fg-faint">{sublabel}</div>}
    </div>
  );
}
