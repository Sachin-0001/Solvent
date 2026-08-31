"use client";

import { useEffect, useState } from "react";
import { AskRail } from "@/components/AskRail";
import { ExceptionLedger } from "@/components/ExceptionLedger";
import { ForecastPanel } from "@/components/ForecastPanel";
import { Header } from "@/components/Header";
import { LedgerBankPairs } from "@/components/LedgerBankPairs";
import { PipelineRail } from "@/components/PipelineRail";
import { ResolutionWaterfall } from "@/components/ResolutionWaterfall";
import { TaxLedger } from "@/components/TaxLedger";
import {
  api,
  type ForecastResponse,
  type ForecasterMetrics,
  type PipelineStatus,
  type ReconciliationException,
  type ReconciliationSummary,
  type TaxSummary,
} from "@/lib/api";

const POLL_INTERVAL_MS = 10_000;

export default function DashboardPage() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [summary, setSummary] = useState<ReconciliationSummary | null>(null);
  const [exceptions, setExceptions] = useState<ReconciliationException[]>([]);
  const [taxSummary, setTaxSummary] = useState<TaxSummary | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [forecasterMetrics, setForecasterMetrics] = useState<ForecasterMetrics | null>(null);
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [p, s, e, t, f, fm] = await Promise.all([
          api.pipelineStatus(),
          api.reconciliationSummary(),
          api.reconciliationExceptions(),
          api.taxSummary(),
          api.forecast(),
          api.forecasterMetrics(),
        ]);
        if (cancelled) return;
        setStatus(p);
        setSummary(s);
        setExceptions(e);
        setTaxSummary(t);
        setForecast(f);
        setForecasterMetrics(fm);
        setHealthy(true);
        setLastUpdated(new Date());
        setError(null);
      } catch {
        if (!cancelled) {
          setHealthy(false);
          setError("Can't reach the Solvent API — is uvicorn running on :8000?");
        }
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
    <div className="mx-auto max-w-[1600px]">
      <Header
        lastUpdated={lastUpdated}
        healthy={healthy}
        sourceCounts={status?.ingest.source_counts ?? null}
      />

      <PipelineRail status={status} />

      <main className="grid grid-cols-1 gap-4 px-6 py-5 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          {error && (
            <div className="border border-accent-red/30 bg-accent-red-dim px-4 py-3 text-sm text-accent-red">
              {error}
            </div>
          )}

          <ResolutionWaterfall summary={summary} />
          <LedgerBankPairs />
          <ExceptionLedger exceptions={exceptions} />
          <ForecastPanel
            days={forecast?.days ?? []}
            referenceDate={forecast?.reference_date}
            modelMetrics={forecasterMetrics}
          />
          <TaxLedger summary={taxSummary} />
        </div>

        <div className="lg:sticky lg:top-[140px] lg:h-[calc(100vh-160px)]">
          <AskRail />
        </div>
      </main>

      <footer className="border-t border-rule px-6 py-5 text-center text-[11px] text-fg-faint">
        Solvent — AI finance-controller pipeline · Razorpay AI Buildathon Track 04
      </footer>
    </div>
  );
}
