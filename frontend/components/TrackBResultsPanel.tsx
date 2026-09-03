"use client";

import { useState } from "react";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { ToolCallLog } from "@/components/ui/ToolCallLog";
import { api, type ToolCallTrace, type TrackBResult } from "@/lib/api";
import { formatINR } from "@/lib/format";

export function TrackBResultsPanel({ result, onBack }: { result: TrackBResult; onBack: () => void }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [trace, setTrace] = useState<ToolCallTrace[]>([]);
  const [asking, setAsking] = useState(false);

  async function ask() {
    if (!question.trim()) return;
    setAsking(true);
    try {
      const res = await api.trackBAsk(question, result.records);
      setAnswer(res.answer);
      setTrace(res.trace);
    } catch {
      setAnswer("Couldn't reach the Q&A endpoint.");
      setTrace([]);
    } finally {
      setAsking(false);
    }
  }

  const totalForecast = result.forecast.days?.reduce((sum, d) => sum + d.expected_amount, 0) ?? 0;

  return (
    <div className="mx-auto max-w-5xl space-y-4 px-6 py-8">
      <button onClick={onBack} className="flex items-center gap-1.5 text-xs text-fg-muted hover:text-fg">
        <ArrowLeft size={13} /> Back
      </button>

      <div className="flex items-center gap-2 text-xs text-fg-faint">
        <span className="border border-rule px-2 py-1 uppercase tracking-wider">
          {result.source === "razorpay_connect" ? "Live Razorpay connection" : "CSV upload"}
        </span>
        {result.date_range && (
          <span>
            {result.date_range.start} → {result.date_range.end}
          </span>
        )}
        {result.transactions_fetched !== undefined && <span>{result.transactions_fetched} transactions fetched</span>}
      </div>

      <Panel>
        <PanelHeader title="Reconciliation" />
        <div className="px-5 py-4 text-sm text-fg-muted">
          {result.reconciliation.note}
          {result.reconciliation.matched !== undefined && (
            <div className="figure mt-2 text-fg">
              {result.reconciliation.matched}/{result.reconciliation.total_ledger_rows} ledger rows matched ·{" "}
              {result.reconciliation.exception_count} exceptions
              <div className="mt-1 text-xs text-fg-faint">
                exact {result.reconciliation.tier_counts?.exact ?? 0} · fuzzy{" "}
                {result.reconciliation.tier_counts?.fuzzy ?? 0} · llm {result.reconciliation.tier_counts?.llm ?? 0}
              </div>
            </div>
          )}
        </div>
        {result.exceptions.length > 0 && (
          <div className="border-t border-rule px-5 py-3">
            {result.exceptions.map((e, i) => (
              <div key={i} className="figure py-1 text-xs text-fg-muted">
                <span className="text-accent-red">{e.reason}</span> · {e.row_id} ({e.order_id}) - {e.explanation}
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel>
        <PanelHeader
          title="Tax classification"
          right={`${result.tax_classification.resolved_by_rules} by rule · ${result.tax_classification.resolved_by_llm} by LLM`}
        />
        <div className="flex flex-wrap gap-4 px-5 py-4">
          {Object.entries(result.tax_classification.category_counts).map(([cat, count]) => (
            <div key={cat} className="text-xs">
              <div className="text-fg-muted">{cat}</div>
              <div className="figure text-lg font-semibold text-fg">{count}</div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="7-day forecast" />
        {result.forecast.error ? (
          <div className="px-5 py-4 text-xs text-accent-amber">{result.forecast.error}</div>
        ) : (
          <div className="px-5 py-4">
            <div className="figure text-xl font-semibold text-fg">{formatINR(totalForecast)}</div>
            <div className="mt-2 flex flex-wrap gap-3">
              {result.forecast.days?.map((d) => (
                <div key={d.date} className="text-xs">
                  <div className="text-fg-faint">{d.date}</div>
                  <div className="figure text-fg">{formatINR(d.expected_amount)}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Panel>

      <Panel>
        <PanelHeader title="Ask about this data" />
        <div className="flex gap-2 px-5 py-4">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()}
            placeholder="Ask about these transactions…"
            className="figure flex-1 border border-border-strong bg-bg-elevated px-2.5 py-1.5 text-[13px] text-fg placeholder:font-sans placeholder:text-fg-faint focus:border-accent-green/50 focus:outline-none"
          />
          <button
            onClick={ask}
            disabled={asking || !question.trim()}
            className="flex items-center gap-1.5 border border-accent-green/30 bg-accent-green-dim px-3 py-1.5 text-xs font-medium text-accent-green disabled:opacity-40"
          >
            {asking && <Loader2 size={12} className="animate-spin" />}
            Ask
          </button>
        </div>
        {answer && (
          <div className="border-t border-rule px-5 py-3">
            {trace.length > 0 && <ToolCallLog trace={trace} />}
            <div className="text-sm text-fg">{answer}</div>
          </div>
        )}
      </Panel>
    </div>
  );
}
