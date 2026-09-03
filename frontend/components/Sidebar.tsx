"use client";

import { useCallback, useEffect, useState } from "react";
import {
  GitCompare,
  Landmark,
  LayoutDashboard,
  Receipt,
  Scale,
  Sparkles,
  TrendingUp,
  UserCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { api } from "@/lib/api";

interface NavItem {
  /** DOM id of the dashboard section this scrolls to. */
  id: string;
  label: string;
  icon: LucideIcon;
}

export type DashboardView = "dashboard" | "review-queue";

/** Overview jumps to the top of the scroll container rather than a section. */
const OVERVIEW: NavItem = { id: "top", label: "Overview", icon: LayoutDashboard };

const SECTION_LABEL = "Finance controller";
const SECTION_NAV: NavItem[] = [
  { id: "reconciliation", label: "Reconciliation", icon: GitCompare },
  { id: "cash-position", label: "Cash position", icon: Landmark },
  { id: "forecast", label: "Forecast", icon: TrendingUp },
  { id: "tax", label: "Tax classification", icon: Scale },
  { id: "exceptions", label: "Exceptions", icon: Receipt },
  { id: "ledger-bank", label: "Ledger ⇄ Bank", icon: Receipt },
];

const ALL_IDS = [OVERVIEW, ...SECTION_NAV].map((i) => i.id);

function NavLink({
  item,
  active,
  onSelect,
  count,
}: {
  item: NavItem;
  active: boolean;
  onSelect: (id: string) => void;
  count?: number;
}) {
  const Icon = item.icon;
  return (
    <button
      onClick={() => onSelect(item.id)}
      aria-current={active ? "true" : undefined}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-[var(--radius-control)] px-2.5 py-[7px] text-left text-[13px] transition-colors",
        active ? "bg-accent-dim text-fg" : "text-fg-muted hover:bg-card-hover hover:text-fg"
      )}
    >
      <Icon size={15} className={cn("shrink-0", active ? "text-accent" : "text-fg-faint")} />
      <span className="truncate">{item.label}</span>
      {typeof count === "number" && count > 0 && (
        <span
          className={cn(
            "figure ml-auto rounded-full px-1.5 py-0.5 text-[11px] leading-none",
            active ? "bg-accent text-white" : "bg-card-hover text-fg-muted"
          )}
        >
          {count}
        </span>
      )}
    </button>
  );
}

export function Sidebar({
  onOpenAsk,
  view,
  onSelectView,
}: {
  onOpenAsk: () => void;
  view: DashboardView;
  onSelectView: (view: DashboardView) => void;
}) {
  const [active, setActive] = useState("top");
  const [pendingReviews, setPendingReviews] = useState<number | null>(null);

  const loadPendingCount = useCallback(async () => {
    try {
      const res = await api.reviewQueue("pending");
      setPendingReviews(res.pending);
    } catch {
      // Sidebar badge is a nice-to-have; a failed poll just leaves it as-is.
    }
  }, []);

  useEffect(() => {
    loadPendingCount();
    const interval = setInterval(loadPendingCount, 10_000);
    return () => clearInterval(interval);
  }, [loadPendingCount]);

  /**
   * Scrolls the main column (not the document) to a section. Also switches
   * back to the dashboard view, since sections only exist there - Review
   * queue is a separate full-page view, not a scroll target.
   */
  function scrollTo(id: string) {
    onSelectView("dashboard");
    setActive(id);
    const container = document.getElementById("dashboard-scroll");
    if (!container) return;
    if (id === "top") {
      container.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    const target = document.getElementById(id);
    if (!target) return;
    // Offset by the sticky-ish header height so the section title isn't clipped.
    const top = target.offsetTop - 12;
    container.scrollTo({ top, behavior: "smooth" });
  }

  /** Keeps the highlighted nav item in sync with what's actually on screen. */
  useEffect(() => {
    if (view !== "dashboard") return;
    const container = document.getElementById("dashboard-scroll");
    if (!container) return;

    function onScroll() {
      if (!container) return;
      if (container.scrollTop < 80) {
        setActive("top");
        return;
      }
      // The section whose top edge is nearest just below the viewport top wins.
      let best = "top";
      let bestDelta = Number.POSITIVE_INFINITY;
      for (const id of ALL_IDS) {
        if (id === "top") continue;
        const el = document.getElementById(id);
        if (!el) continue;
        const delta = Math.abs(el.offsetTop - container.scrollTop - 12);
        if (delta < bestDelta) {
          bestDelta = delta;
          best = id;
        }
      }
      setActive(best);
    }

    container.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => container.removeEventListener("scroll", onScroll);
  }, [view]);

  return (
    <aside className="hidden h-screen w-[212px] shrink-0 flex-col border-r border-rule bg-bg-sidebar lg:flex">
      <div className="px-4 py-4">
        <span className="wordmark text-[19px] text-fg">Solvent</span>
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        <NavLink
          item={OVERVIEW}
          active={view === "dashboard" && active === OVERVIEW.id}
          onSelect={scrollTo}
        />

        <div className="mt-5">
          <div className="px-2.5 pb-1.5 text-[11px] font-medium uppercase tracking-wider text-fg-faint">
            {SECTION_LABEL}
          </div>
          <div className="flex flex-col gap-0.5">
            {SECTION_NAV.map((item) => (
              <NavLink
                key={item.id}
                item={item}
                active={view === "dashboard" && active === item.id}
                onSelect={scrollTo}
              />
            ))}
          </div>
        </div>

        <div className="mt-5">
          <div className="px-2.5 pb-1.5 text-[11px] font-medium uppercase tracking-wider text-fg-faint">
            Human in the loop
          </div>
          <div className="flex flex-col gap-0.5">
            <NavLink
              item={{ id: "review-queue", label: "Review queue", icon: UserCheck }}
              active={view === "review-queue"}
              onSelect={() => onSelectView("review-queue")}
              count={pendingReviews ?? undefined}
            />
          </div>
        </div>
      </nav>

      <div className="shrink-0 border-t border-rule p-2">
        <button
          onClick={onOpenAsk}
          className="flex w-full items-center gap-2 rounded-[var(--radius-control)] bg-accent px-2.5 py-2 text-[13px] font-medium text-white transition-colors hover:bg-accent-hover"
        >
          <Sparkles size={14} />
          Solvent AI
          <span className="figure ml-auto text-[11px] text-white/70">⌘K</span>
        </button>
      </div>
    </aside>
  );
}
