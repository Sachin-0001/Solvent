import { cn } from "@/lib/cn";

type Tone = "green" | "red" | "amber" | "blue" | "neutral";

const toneClasses: Record<Tone, string> = {
  green: "bg-accent-green-dim text-accent-green border-accent-green/25",
  red: "bg-accent-red-dim text-accent-red border-accent-red/25",
  amber: "bg-accent-amber-dim text-accent-amber border-accent-amber/25",
  blue: "bg-accent-blue-dim text-accent-blue border-accent-blue/25",
  neutral: "bg-white/5 text-fg-muted border-border-strong",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: React.ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px]",
        toneClasses[tone],
        className
      )}
    >
      {children}
    </span>
  );
}

const TIER_TONE: Record<string, Tone> = { exact: "green", fuzzy: "blue", llm: "amber" };

export function TierBadge({ tier }: { tier: string }) {
  return <Badge tone={TIER_TONE[tier] ?? "neutral"}>{tier}</Badge>;
}

export function SideMarker({ side }: { side: string }) {
  const letter = side === "ledger" ? "L" : side === "bank" ? "B" : side.slice(0, 1).toUpperCase();
  return (
    <span
      className="figure inline-flex h-5 w-5 items-center justify-center rounded border border-border-strong text-[10px] text-fg-muted"
      title={side}
    >
      {letter}
    </span>
  );
}

export function GateMark({ gate }: { gate: "passed" | "pending" }) {
  return (
    <span className="inline-flex items-center gap-1 text-[11px] uppercase tracking-wider">
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          gate === "passed" ? "bg-accent-green" : "bg-accent-amber"
        )}
      />
      <span className={gate === "passed" ? "text-accent-green" : "text-accent-amber"}>
        {gate}
      </span>
    </span>
  );
}
