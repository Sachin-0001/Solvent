"use client";

import { useState } from "react";
import { ArrowLeft, KeyRound, Loader2, Upload } from "lucide-react";
import { api, type TrackBResult } from "@/lib/api";

type Mode = "choose" | "keys" | "upload";

export function TrackBConnect({
  onBack,
  onResult,
}: {
  onBack: () => void;
  onResult: (result: TrackBResult) => void;
}) {
  const [mode, setMode] = useState<Mode>("choose");
  const [keyId, setKeyId] = useState("");
  const [keySecret, setKeySecret] = useState("");
  const [ledgerFile, setLedgerFile] = useState<File | null>(null);
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submitKeys() {
    setLoading(true);
    setError(null);
    try {
      const result = await api.trackBConnect(keyId, keySecret);
      // Keys are never held anywhere else, never redisplayed - clear
      // immediately after the one request that used them.
      setKeyId("");
      setKeySecret("");
      onResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connection failed");
    } finally {
      setLoading(false);
    }
  }

  async function submitUpload() {
    if (!ledgerFile || !bankFile) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.trackBUpload(ledgerFile, bankFile);
      onResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl px-6 py-10">
      <button
        onClick={mode === "choose" ? onBack : () => setMode("choose")}
        className="mb-6 flex items-center gap-1.5 text-xs text-fg-muted hover:text-fg"
      >
        <ArrowLeft size={13} /> Back
      </button>

      {mode === "choose" && (
        <div className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-fg">Connect my account</h2>
          <button
            onClick={() => setMode("keys")}
            className="flex items-center gap-3 border border-rule bg-card px-4 py-4 text-left hover:border-accent-blue/50"
          >
            <KeyRound size={16} className="text-accent-blue" />
            <div>
              <div className="text-sm font-medium text-fg">Enter Razorpay API keys</div>
              <div className="text-xs text-fg-faint">Test-mode key + secret, used once, never stored</div>
            </div>
          </button>
          <button
            onClick={() => setMode("upload")}
            className="flex items-center gap-3 border border-rule bg-card px-4 py-4 text-left hover:border-accent-blue/50"
          >
            <Upload size={16} className="text-accent-blue" />
            <div>
              <div className="text-sm font-medium text-fg">Upload ledger + bank statement CSVs</div>
              <div className="text-xs text-fg-faint">Runs full reconciliation between the two files</div>
            </div>
          </button>
        </div>
      )}

      {mode === "keys" && (
        <div className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-fg">Razorpay API keys</h2>
          <p className="text-xs text-fg-muted">
            Test-mode credentials only. Sent once to fetch your payments/settlements/refunds,
            never logged, never stored, never shown again after you submit.
          </p>
          <input
            type="text"
            value={keyId}
            onChange={(e) => setKeyId(e.target.value)}
            placeholder="Key ID (rzp_test_...)"
            className="figure border border-border-strong bg-bg-elevated px-3 py-2 text-sm text-fg placeholder:font-sans placeholder:text-fg-faint focus:border-accent-blue/50 focus:outline-none"
            autoComplete="off"
          />
          <input
            type="password"
            value={keySecret}
            onChange={(e) => setKeySecret(e.target.value)}
            placeholder="Key Secret"
            className="figure border border-border-strong bg-bg-elevated px-3 py-2 text-sm text-fg placeholder:font-sans placeholder:text-fg-faint focus:border-accent-blue/50 focus:outline-none"
            autoComplete="off"
          />
          <button
            onClick={submitKeys}
            disabled={loading || !keyId.trim() || !keySecret.trim()}
            className="flex items-center justify-center gap-2 border border-accent-blue/40 bg-accent-blue-dim px-4 py-2 text-sm font-medium text-accent-blue disabled:opacity-40"
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            Connect
          </button>
        </div>
      )}

      {mode === "upload" && (
        <div className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-fg">Upload CSVs</h2>
          <p className="text-xs text-fg-muted">
            Ledger CSV needs: row_id, order_id, amount, timestamp (optional: payment_method,
            fee_amount, tax_on_fee, refund_amount, status). Bank CSV needs: row_id, order_id,
            amount, timestamp (optional: utr_reference).
          </p>
          <label className="border border-dashed border-border-strong px-4 py-3 text-xs text-fg-muted">
            Ledger CSV
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setLedgerFile(e.target.files?.[0] ?? null)}
              className="mt-1 block w-full text-xs"
            />
          </label>
          <label className="border border-dashed border-border-strong px-4 py-3 text-xs text-fg-muted">
            Bank statement CSV
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setBankFile(e.target.files?.[0] ?? null)}
              className="mt-1 block w-full text-xs"
            />
          </label>
          <button
            onClick={submitUpload}
            disabled={loading || !ledgerFile || !bankFile}
            className="flex items-center justify-center gap-2 border border-accent-blue/40 bg-accent-blue-dim px-4 py-2 text-sm font-medium text-accent-blue disabled:opacity-40"
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            Run reconciliation
          </button>
        </div>
      )}

      {error && (
        <div className="mt-4 border border-accent-red/30 bg-accent-red-dim px-3 py-2 text-xs text-accent-red">
          {error}
        </div>
      )}
    </div>
  );
}
