"use client";

import { useEffect, useState } from "react";
import { AskWidget } from "@/components/AskWidget";
import { CashPositionPanel } from "@/components/CashPositionPanel";
import { DashboardHeader } from "@/components/DashboardHeader";
import { ExceptionLedger } from "@/components/ExceptionLedger";
import { ForecastPanel } from "@/components/ForecastPanel";
import { LandingChoice } from "@/components/LandingChoice";
import { Sidebar, type DashboardView } from "@/components/Sidebar";
import { LedgerBankPairs } from "@/components/LedgerBankPairs";
import { PipelineRail } from "@/components/PipelineRail";
import { ResolutionWaterfall } from "@/components/ResolutionWaterfall";
import { ReviewQueue } from "@/components/ReviewQueue";
import { TaxLedger } from "@/components/TaxLedger";
import { TrackBConnect } from "@/components/TrackBConnect";
import { TrackBResultsPanel } from "@/components/TrackBResultsPanel";
import {
  api,
  type CashPosition,
  type ForecastResponse,
  type ForecasterMetrics,
  type GmvForecast,
  type PipelineStatus,
  type ReconciliationException,
  type ReconciliationSummary,
  type TaxSummary,
  type TrackBResult,
} from "@/lib/api";

const POLL_INTERVAL_MS = 10_000;

type ViewMode = "landing" | "sample" | "connect" | "track-b-results";

export default function DashboardPage() {
  const [mode, setMode] = useState<ViewMode>("landing");
  const [trackBResult, setTrackBResult] = useState<TrackBResult | null>(null);
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [summary, setSummary] = useState<ReconciliationSummary | null>(null);
  const [exceptions, setExceptions] = useState<ReconciliationException[] | null>(null);
  const [taxSummary, setTaxSummary] = useState<TaxSummary | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [forecasterMetrics, setForecasterMetrics] = useState<ForecasterMetrics | null>(null);
  const [cashPosition, setCashPosition] = useState<CashPosition | null>(null);
  const [gmvForecast, setGmvForecast] = useState<GmvForecast | null>(null);
  const [currentCash, setCurrentCash] = useState(1_000_000);
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [askOpen, setAskOpen] = useState(false);
  const [view, setView] = useState<DashboardView>("dashboard");

  useEffect(() => {
    if (mode !== "sample") return;
    let cancelled = false;

    async function load() {
      try {
        const [p, s, e, t, f, fm, cp, gf] = await Promise.all([
          api.pipelineStatus(),
          api.reconciliationSummary(),
          api.reconciliationExceptions(),
          api.taxSummary(),
          api.forecast(),
          api.forecasterMetrics(),
          api.cashPosition(currentCash),
          api.forecastGmv(),
        ]);
        if (cancelled) return;
        setStatus(p);
        setSummary(s);
        setExceptions(e);
        setTaxSummary(t);
        setForecast(f);
        setForecasterMetrics(fm);
        setCashPosition(cp);
        setGmvForecast(gf);
        setHealthy(true);
        setLastUpdated(new Date());
        setError(null);
      } catch {
        if (!cancelled) {
          setHealthy(false);
          setError("Can't reach the Solvent API - is uvicorn running on :8000?");
        }
      }
    }

    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [mode, currentCash]);

  useEffect(() => {
    function onKeydown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setAskOpen(true);
      }
    }
    window.addEventListener("keydown", onKeydown);
    return () => window.removeEventListener("keydown", onKeydown);
  }, []);

  if (mode === "landing") {
    return (
      <LandingChoice
        onTrySample={() => setMode("sample")}
        onConnectAccount={() => setMode("connect")}
      />
    );
  }

  if (mode === "connect") {
    return (
      <TrackBConnect
        onBack={() => setMode("landing")}
        onResult={(result) => {
          setTrackBResult(result);
          setMode("track-b-results");
        }}
      />
    );
  }

  if (mode === "track-b-results" && trackBResult) {
    return (
      <TrackBResultsPanel
        result={trackBResult}
        onBack={() => {
          setTrackBResult(null);
          setMode("landing");
        }}
      />
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        onOpenAsk={() => setAskOpen(true)}
        view={view}
        onSelectView={setView}
      />

      {/* Only this column scrolls - the sidebar stays fixed. Sidebar nav
          scrolls this element by id (see Sidebar.tsx's scrollTo). */}
      <div id="dashboard-scroll" className="min-w-0 flex-1 overflow-y-auto">
        <DashboardHeader
          lastUpdated={lastUpdated}
          healthy={healthy}
          transactionCount={status?.ingest.total_transactions ?? null}
          onSwitchSource={() => setMode("landing")}
        />

        {view === "review-queue" ? (
          <main className="space-y-3 px-7 py-5">
            {error && (
              <div className="rounded-[var(--radius-card)] border border-accent-red/30 bg-accent-red-dim px-4 py-3 text-sm text-accent-red">
                {error}
              </div>
            )}
            <ReviewQueue />
          </main>
        ) : (
          <main className="space-y-3 px-7 py-5">
            {error && (
              <div className="rounded-[var(--radius-card)] border border-accent-red/30 bg-accent-red-dim px-4 py-3 text-sm text-accent-red">
                {error}
              </div>
            )}

            <PipelineRail status={status} cashPosition={cashPosition} />

            {/* Insight grid - two columns on wide screens, matching the reference layout. */}
            <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
              <div id="reconciliation" className="scroll-mt-4 h-full">
                <ResolutionWaterfall summary={summary} />
              </div>
              <div id="cash-position" className="scroll-mt-4 h-full">
                <CashPositionPanel
                  cashPosition={cashPosition}
                  gmvForecast={gmvForecast}
                  onCurrentCashChange={setCurrentCash}
                />
              </div>
              <div id="forecast" className="scroll-mt-4 h-full">
                <ForecastPanel
                  days={forecast?.days ?? null}
                  referenceDate={forecast?.reference_date}
                  modelMetrics={forecasterMetrics}
                />
              </div>
              <div id="tax" className="scroll-mt-4 h-full">
                <TaxLedger summary={taxSummary} />
              </div>
              <div id="exceptions" className="scroll-mt-4 xl:col-span-2">
                <ExceptionLedger exceptions={exceptions} />
              </div>
              <div id="ledger-bank" className="scroll-mt-4 xl:col-span-2">
                <LedgerBankPairs />
              </div>
            </div>

            <footer className="mt-4 border-t border-rule pt-6 pb-5">
              <span className="wordmark text-[56px] leading-none text-fg">Solvent</span>
              <p className="mt-3 text-xs text-fg-faint">AI finance-controller pipeline</p>
            </footer>
          </main>
        )}
      </div>

      <AskWidget open={askOpen} onClose={() => setAskOpen(false)} />
    </div>
  );
}
