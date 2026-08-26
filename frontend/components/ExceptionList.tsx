import type { ReconciliationException } from "@/lib/api";

const REASON_META: Record<string, { label: string; className: string }> = {
  missing_counterpart: {
    label: "Missing counterpart",
    className: "bg-accent-red/10 text-accent-red border-accent-red/20",
  },
  likely_duplicate: {
    label: "Likely duplicate",
    className: "bg-accent-amber/10 text-accent-amber border-accent-amber/20",
  },
  unexplained: {
    label: "Unexplained",
    className: "bg-fg-faint/10 text-fg-muted border-border-strong",
  },
};

export function ExceptionList({ exceptions }: { exceptions: ReconciliationException[] }) {
  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div className="text-xs font-medium uppercase tracking-wider text-fg-muted">
          Exception List
        </div>
        <div className="font-mono text-xs text-fg-faint">{exceptions.length} unresolved</div>
      </div>
      <div className="max-h-96 overflow-y-auto">
        {exceptions.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-fg-faint">
            No exceptions — everything reconciled cleanly.
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-card">
              <tr className="text-[11px] uppercase tracking-wider text-fg-faint">
                <th className="px-5 py-2 font-medium">Row</th>
                <th className="px-2 py-2 font-medium">Side</th>
                <th className="px-2 py-2 font-medium">Order</th>
                <th className="px-2 py-2 font-medium">Reason</th>
                <th className="px-5 py-2 font-medium">Explanation</th>
              </tr>
            </thead>
            <tbody>
              {exceptions.map((e) => {
                const meta = REASON_META[e.reason] ?? {
                  label: e.reason,
                  className: "bg-fg-faint/10 text-fg-muted border-border-strong",
                };
                return (
                  <tr key={e.id} className="border-t border-border hover:bg-card-hover">
                    <td className="px-5 py-2.5 font-mono text-xs text-fg">{e.row_id}</td>
                    <td className="px-2 py-2.5 text-xs text-fg-muted">{e.side}</td>
                    <td className="px-2 py-2.5 font-mono text-xs text-fg-muted">
                      {e.order_id ?? "—"}
                    </td>
                    <td className="px-2 py-2.5">
                      <span
                        className={`inline-block rounded-full border px-2 py-0.5 text-[11px] whitespace-nowrap ${meta.className}`}
                      >
                        {meta.label}
                      </span>
                    </td>
                    <td className="px-5 py-2.5 text-xs text-fg-muted">{e.explanation}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
