"use client";

import { Database, KeyRound, Upload } from "lucide-react";

export function LandingChoice({
  onTrySample,
  onConnectAccount,
}: {
  onTrySample: () => void;
  onConnectAccount: () => void;
}) {
  return (
    <div className="mx-auto flex min-h-[70vh] max-w-3xl flex-col items-center justify-center gap-8 px-6 text-center">
      <div>
        <div className="wordmark mb-1 text-[38px] leading-none text-fg">Solvent</div>
        <div className="mb-5 text-xs font-medium uppercase tracking-wider text-fg-faint">
          AI Finance Controller
        </div>
        <h1 className="text-2xl font-semibold text-fg">
          Reconcile settlements, classify GST, forecast cash flow
        </h1>
        <p className="mt-2 text-sm text-fg-muted">
          Same pipeline either way - pick how you want to feed it data.
        </p>
      </div>

      <div className="grid w-full gap-4 sm:grid-cols-2">
        <button
          onClick={onTrySample}
          className="group flex flex-col items-start gap-3 border border-rule bg-card px-5 py-5 text-left transition-colors hover:border-accent-green/50"
        >
          <div className="flex h-9 w-9 items-center justify-center border border-accent-green/25 bg-accent-green-dim text-accent-green">
            <Database size={16} />
          </div>
          <div>
            <div className="text-sm font-semibold text-fg">Try sample data</div>
            <div className="mt-1 text-xs text-fg-muted">
              250 synthetic transactions with known ground truth, validated
              reconciliation/tax/forecast metrics - the demo dataset.
            </div>
          </div>
          <span className="mt-auto text-xs font-medium text-accent-green group-hover:underline">
            Open demo dashboard →
          </span>
        </button>

        <button
          onClick={onConnectAccount}
          className="group flex flex-col items-start gap-3 border border-rule bg-card px-5 py-5 text-left transition-colors hover:border-accent-blue/50"
        >
          <div className="flex h-9 w-9 items-center justify-center border border-accent-blue/25 bg-accent-blue-dim text-accent-blue">
            <KeyRound size={16} />
          </div>
          <div>
            <div className="text-sm font-semibold text-fg">Connect my account</div>
            <div className="mt-1 text-xs text-fg-muted">
              Use your own Razorpay test-mode keys, or upload your own
              ledger/bank-statement CSVs - nothing is stored.
            </div>
          </div>
          <span className="mt-auto flex items-center gap-1 text-xs font-medium text-accent-blue group-hover:underline">
            <Upload size={11} /> Connect live data →
          </span>
        </button>
      </div>
    </div>
  );
}
