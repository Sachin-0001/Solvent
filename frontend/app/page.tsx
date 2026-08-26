"use client";

import { useEffect, useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { ExceptionList } from "@/components/ExceptionList";
import { ForecastChart } from "@/components/ForecastChart";
import { Header } from "@/components/Header";
import { KpiCard } from "@/components/KpiCard";
import { TaxBreakdown } from "@/components/TaxBreakdown";
import {
  api,
  type ForecastResponse,
  type ReconciliationException,
  type ReconciliationSummary,
  type TaxSummary,
} from "@/lib/api";

const POLL_INTERVAL_MS = 10_000;

export default function DashboardPage() {
  const [summary, setSummary] = useState<ReconciliationSummary | null>(null);
  const [exceptions, setExceptions] = useState<ReconciliationException[]>([]);
  const [taxSummary, setTaxSummary] = useState<TaxSummary | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [s, e, t, f] = await Promise.all([
          api.reconciliationSummary(),
          api.reconciliationExceptions(),
          api.taxSummary(),
          api.forecast(),
        ]);
        if (cancelled) return;
        setSummary(s);
        setExceptions(e);
        setTaxSummary(t);
        setForecast(f);
        setLastUpdated(new Date());
        setError(null);
      } catch {
        if (!cancelled) setError("Can't reach the Solvent API — is uvicorn running on :8000?");
      }
    }

    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="mx-auto max-w-7xl">
      <Header lastUpdated={lastUpdated} />

      <main className="space-y-6 px-8 py-6">
        {error && (
          <div className="rounded-lg border border-accent-red/30 bg-accent-red/10 px-4 py-3 text-sm text-accent-red">
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <KpiCard
            label="Match Rate"
            value={summary ? `${(summary.match_rate * 100).toFixed(1)}` : "—"}
            suffix="%"
            accent="green"
            sublabel={summary ? `${summary.reported_matches}/${summary.total_ground_truth_txns} txns` : undefined}
          />
          <KpiCard
            label="Precision"
            value={summary ? `${(summary.precision * 100).toFixed(1)}` : "—"}
            suffix="%"
            accent="blue"
            sublabel={summary ? `${summary.false_positives} false positives` : undefined}
          />
          <KpiCard
            label="Recall"
            value={summary ? `${(summary.recall * 100).toFixed(1)}` : "—"}
            suffix="%"
            accent="blue"
            sublabel={summary ? `${summary.false_negatives} false negatives` : undefined}
          />
          <KpiCard
            label="Exceptions"
            value={summary ? `${summary.exception_count}` : "—"}
            accent={summary && summary.exception_count > 0 ? "amber" : "green"}
            sublabel="honest, reasoned, not hidden"
          />
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2">
            {forecast && (
              <ForecastChart days={forecast.days} referenceDate={forecast.reference_date} />
            )}
          </div>
          <div>{taxSummary && <TaxBreakdown summary={taxSummary} />}</div>
        </div>

        <ExceptionList exceptions={exceptions} />

        <ChatPanel />
      </main>

      <footer className="px-8 py-6 text-center text-[11px] text-fg-faint">
        Solvent — AI finance-controller pipeline · Razorpay AI Buildathon Track 04
      </footer>
    </div>
  );
}
