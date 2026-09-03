import type { CSSProperties } from "react";
import { cn } from "@/lib/cn";

/**
 * Shimmer placeholder for a value that hasn't loaded yet. Sized via
 * className (width/height utilities), not props, so call sites can match
 * the exact shape of the real content they're standing in for. `style` is
 * only for cases a utility class can't express, e.g. a randomized bar height.
 */
export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <span
      aria-hidden
      style={style}
      className={cn("skeleton-shimmer inline-block rounded-[var(--radius-control)]", className)}
    />
  );
}
