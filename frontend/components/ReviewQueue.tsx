"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Link2, RotateCcw, X } from "lucide-react";
import {
  api,
  type ReviewDecision,
  type ReviewQueueItem,
  type ReviewQueueResponse,
} from "@/lib/api";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { Badge, SideMarker } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatINRFull } from "@/lib/format";
import { cn } from "@/lib/cn";

const REASON_LABEL: Record<string, string> = {
  missing_counterpart: "Missing counterpart",
  likely_duplicate: "Likely duplicate",
  unexplained: "Unexplained",
};

const DECISION_META: Record<ReviewDecision, { label: string; tone: "green" | "red" | "blue" }> = {
  approved_match: { label: "Approved", tone: "green" },
  written_off: { label: "Written off", tone: "red" },
  manually_paired: { label: "Manually paired", tone: "blue" },
};

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ReviewRow({
  item,
  onDecide,
  onReopen,
  busy,
}: {
  item: ReviewQueueItem;
  onDecide: (
    item: ReviewQueueItem,
    decision: ReviewDecision,
    pairedRowId?: string,
    note?: string
  ) => void;
  onReopen: (item: ReviewQueueItem) => void;
  busy: boolean;
}) {
  const [note, setNote] = useState("");
  const [showPair, setShowPair] = useState(false);
  const resolved = item.review !== null;
  const hasCandidates = item.candidates.length > 0;

  return (
    <div className={cn("px-5 py-3.5", resolved && "opacity-60")}>
      <div className="flex flex-wrap items-center gap-2">
        <SideMarker side={item.side} />
        <span className="figure text-[13px] text-fg">{item.row_id}</span>
        <span className="figure text-xs text-fg-faint">{item.order_id ?? "-"}</span>
        <Badge tone={item.reason === "missing_counterpart" ? "red" : "amber"}>
          {REASON_LABEL[item.reason] ?? item.reason}
        </Badge>
        {item.source_row && (
          <span className="figure text-xs text-fg-muted">
            {formatINRFull(item.source_row.amount)}
          </span>
        )}
        {resolved && item.review && (
          <Badge tone={DECISION_META[item.review.decision]?.tone ?? "neutral"}>
            {DECISION_META[item.review.decision]?.label ?? item.review.decision}
          </Badge>
        )}
      </div>

      <p className="mt-1 text-xs text-fg-muted">{item.explanation}</p>

      {/* The raw narration is the only thing a human has to go on when the
          two sides describe the same transaction in different words (e.g.
          "RZP/ORD_8492/ABC" vs "ABC PVT LTD ORDER 8492") - surface it
          verbatim rather than making the reviewer trust our matching logic. */}
      {item.source_row?.narration && (
        <p className="mt-1 flex items-baseline gap-1.5 text-xs">
          <span className="shrink-0 text-fg-faint">
            {item.side === "ledger" ? "Ledger narration" : "Bank narration"}:
          </span>
          <span className="figure text-fg">{item.source_row.narration}</span>
        </p>
      )}

      {/* Candidate evidence - what makes the call possible. */}
      {hasCandidates && !resolved && (
        <div className="mt-2 rounded-[var(--radius-control)] border border-rule bg-bg-elevated px-2.5 py-2">
          <div className="text-[11px] font-medium uppercase tracking-wider text-fg-faint">
            Possible counterpart{item.candidates.length > 1 ? "s" : ""} on the{" "}
            {item.side === "ledger" ? "bank" : "ledger"} side
          </div>
          <div className="mt-1 flex flex-col gap-1">
            {item.candidates.map((c) => (
              <div key={c.row_id} className="flex flex-wrap items-center gap-2 text-xs text-fg-muted">
                <span className="figure text-fg">{c.row_id}</span>
                <span className="figure">{formatINRFull(c.amount)}</span>
                <span className="figure text-fg-faint">{formatDateTime(c.timestamp)}</span>
                {c.narration && (
                  <span className="figure text-fg-muted">&ldquo;{c.narration}&rdquo;</span>
                )}
                {showPair && (
                  <button
                    disabled={busy}
                    onClick={() => onDecide(item, "manually_paired", c.row_id, note)}
                    className="ml-auto rounded-[var(--radius-control)] border border-accent/40 bg-accent-dim px-1.5 py-0.5 text-[11px] text-accent disabled:opacity-40"
                  >
                    pair with this
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {resolved && item.review ? (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-fg-faint">
          <span>
            {formatDateTime(item.review.decided_at)}
            {item.review.paired_row_id && (
              <>
                {" · paired with "}
                <span className="figure text-fg-muted">{item.review.paired_row_id}</span>
              </>
            )}
          </span>
          {item.review.note && <span className="text-fg-muted">“{item.review.note}”</span>}
          <button
            disabled={busy}
            onClick={() => onReopen(item)}
            className="ml-auto flex items-center gap-1 rounded-[var(--radius-control)] border border-border-strong px-1.5 py-0.5 transition-colors hover:text-fg disabled:opacity-40"
          >
            <RotateCcw size={10} />
            reopen
          </button>
        </div>
      ) : (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add a note (optional)…"
            className="min-w-[180px] flex-1 rounded-[var(--radius-control)] border border-border-strong bg-bg-elevated px-2 py-1 text-xs text-fg placeholder:text-fg-faint focus:border-accent focus:outline-none"
          />
          {hasCandidates && (
            <button
              disabled={busy}
              onClick={() => onDecide(item, "approved_match", item.candidates[0].row_id, note)}
              title="Confirm this really is the same transaction"
              className="flex items-center gap-1 rounded-[var(--radius-control)] border border-accent-green/35 bg-accent-green-dim px-2 py-1 text-xs text-accent-green transition-colors hover:border-accent-green/60 disabled:opacity-40"
            >
              <Check size={11} />
              Approve match
            </button>
          )}
          {item.candidates.length > 1 && (
            <button
              disabled={busy}
              onClick={() => setShowPair((v) => !v)}
              className="flex items-center gap-1 rounded-[var(--radius-control)] border border-accent/35 bg-accent-dim px-2 py-1 text-xs text-accent transition-colors hover:border-accent/60 disabled:opacity-40"
            >
              <Link2 size={11} />
              Pair manually
            </button>
          )}
          <button
            disabled={busy}
            onClick={() => onDecide(item, "written_off", undefined, note)}
            title="No counterpart exists - close this as written off"
            className="flex items-center gap-1 rounded-[var(--radius-control)] border border-accent-red/35 bg-accent-red-dim px-2 py-1 text-xs text-accent-red transition-colors hover:border-accent-red/60 disabled:opacity-40"
          >
            <X size={11} />
            Write off
          </button>
        </div>
      )}
    </div>
  );
}

export function ReviewQueue() {
  const [data, setData] = useState<ReviewQueueResponse | null>(null);
  const [filter, setFilter] = useState<"pending" | "resolved">("pending");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.reviewQueue(filter));
      setError(null);
    } catch {
      setError("Couldn't load the review queue.");
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  async function onDecide(
    item: ReviewQueueItem,
    decision: ReviewDecision,
    pairedRowId?: string,
    note?: string
  ) {
    setBusy(true);
    try {
      await api.submitReview({
        row_id: item.row_id,
        side: item.side,
        decision,
        order_id: item.order_id,
        paired_row_id: pairedRowId ?? null,
        note: note?.trim() ? note.trim() : null,
        reviewer: "demo-reviewer",
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save the decision.");
    } finally {
      setBusy(false);
    }
  }

  async function onReopen(item: ReviewQueueItem) {
    setBusy(true);
    try {
      await api.reopenReview(item.row_id, item.side);
      await load();
    } catch {
      setError("Failed to reopen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel>
      <PanelHeader
        eyebrow="Human in the loop · needs a decision"
        title="Review Queue"
        subtitle="Exceptions the engine deliberately refused to auto-match. A reviewer decides, and the decision is recorded with an audit trail."
        count={data?.pending}
        right={
          data ? `${data.pending} pending · ${data.resolved} resolved` : undefined
        }
      />

      <div className="flex gap-2 border-b border-rule px-5 py-2.5">
        {(["pending", "resolved"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "rounded-[var(--radius-control)] border px-2 py-1 text-xs capitalize transition-colors",
              filter === f
                ? "border-accent/50 bg-accent-dim text-accent"
                : "border-border-strong text-fg-muted hover:text-fg"
            )}
          >
            {f}
            {data && ` (${f === "pending" ? data.pending : data.resolved})`}
          </button>
        ))}
      </div>

      {error && (
        <div className="border-b border-rule bg-accent-red-dim px-5 py-2 text-xs text-accent-red">
          {error}
        </div>
      )}

      <div className="max-h-[calc(100vh-220px)] divide-y divide-rule overflow-y-auto">
        {!data &&
          Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="px-5 py-3.5">
              <div className="flex items-center gap-2">
                <Skeleton className="h-3.5 w-3.5 rounded-full" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-5 w-28 rounded-full" />
              </div>
              <Skeleton className="mt-2 h-3.5 w-3/4" />
            </div>
          ))}
        {data?.items.length === 0 && (
          <div className="px-5 py-8 text-center text-sm text-fg-faint">
            {filter === "pending"
              ? "Nothing pending - every exception has been reviewed."
              : "No decisions recorded yet."}
          </div>
        )}
        {data?.items.map((item) => (
          <ReviewRow
            key={`${item.row_id}-${item.side}`}
            item={item}
            onDecide={onDecide}
            onReopen={onReopen}
            busy={busy}
          />
        ))}
      </div>
    </Panel>
  );
}
