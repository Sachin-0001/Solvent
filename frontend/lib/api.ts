const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface ReconciliationSummary {
  total_ground_truth_txns: number;
  should_fully_reconcile: number;
  reported_matches: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  precision: number;
  recall: number;
  match_rate: number;
  tier_breakdown: Record<string, number>;
  exception_count: number;
  unresolved_should_reconcile_txn_ids: string[];
}

export interface ReconciliationException {
  id: number;
  row_id: string;
  side: string;
  order_id: string | null;
  reason: string;
  explanation: string;
}

export interface TaxSummary {
  total: number;
  category_breakdown: Record<string, number>;
  resolved_by_rules: number;
  resolved_by_llm: number;
}

export interface ForecastDay {
  date: string;
  expected_amount: number;
  lower_bound: number;
  upper_bound: number;
}

export interface ForecastResponse {
  reference_date: string;
  days: ForecastDay[];
}

export interface HealthResponse {
  ok: boolean;
}

export interface ForecasterModelReport {
  label: string;
  target: string;
  n_train: number;
  n_test: number;
  curvature_detected: boolean;
  baseline_linear: { mae: number; mape_pct: number };
  polynomial_degree2: { mae: number; mape_pct: number } | null;
  chosen_model: string;
  chosen_mae: number;
  chosen_mape_pct: number;
  model_path: string;
}

export interface ForecasterMetrics {
  model_a: ForecasterModelReport | null;
  model_b: ForecasterModelReport | null;
}

export type Gate = "passed" | "pending";

export interface PipelineStatus {
  ingest: {
    total_transactions: number;
    source_counts: Record<string, number>;
    ledger_rows: number;
    bank_rows: number;
    gate: Gate;
  };
  reconcile: ReconciliationSummary & { gate: Gate };
  classify: {
    total: number;
    category_counts: Record<string, number>;
    resolved_by_rules: number;
    resolved_by_llm: number;
    gate: Gate;
  };
  forecast: ForecasterMetrics & { gate: Gate };
  qa: { indexed_records: number; gate: Gate };
}

export interface LedgerRow {
  row_id: string;
  txn_id_hint: string;
  order_id: string;
  amount: number;
  timestamp: string;
  payment_method: string | null;
  status: string | null;
  fee_amount: number | null;
  tax_on_fee: number | null;
  refund_amount: number | null;
  narration: string | null;
}

export interface BankRow {
  row_id: string;
  txn_id_hint: string;
  order_id: string;
  amount: number;
  timestamp: string;
  utr_reference: string | null;
  type: string | null;
  narration: string | null;
}

export interface MatchTolerance {
  amount_abs: number;
  amount_pct: number;
  timestamp_hours: number;
}

export interface ReconciliationMatch {
  id: number;
  ledger_row_id: string;
  bank_row_id: string;
  order_id: string | null;
  tier: string;
  amount_diff: number;
  timestamp_diff_hours: number;
  explanation: string | null;
  ledger: LedgerRow | null;
  bank: BankRow | null;
  tolerance: MatchTolerance | null;
}

export interface ReconciliationMatchesResponse {
  total: number;
  items: ReconciliationMatch[];
}

export interface TaxClassificationRecord {
  txn_id: string;
  category: string;
  method: string;
  reasoning: string;
}

export interface TaxClassificationsResponse {
  total: number;
  items: TaxClassificationRecord[];
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => getJSON<HealthResponse>("/api/health"),
  reconciliationSummary: () => getJSON<ReconciliationSummary>("/api/reconciliation/summary"),
  reconciliationExceptions: () =>
    getJSON<ReconciliationException[]>("/api/reconciliation/exceptions"),
  reconciliationMatches: (opts?: { tier?: string; sort?: "drift"; limit?: number }) => {
    const params = new URLSearchParams();
    if (opts?.tier) params.set("tier", opts.tier);
    if (opts?.sort) params.set("sort", opts.sort);
    if (opts?.limit) params.set("limit", String(opts.limit));
    const qs = params.toString();
    return getJSON<ReconciliationMatchesResponse>(
      `/api/reconciliation/matches${qs ? `?${qs}` : ""}`
    );
  },
  taxSummary: () => getJSON<TaxSummary>("/api/tax/summary"),
  taxClassifications: (opts?: { category?: string; limit?: number }) => {
    const params = new URLSearchParams();
    if (opts?.category) params.set("category", opts.category);
    if (opts?.limit) params.set("limit", String(opts.limit));
    const qs = params.toString();
    return getJSON<TaxClassificationsResponse>(`/api/tax/classifications${qs ? `?${qs}` : ""}`);
  },
  forecast: () => getJSON<ForecastResponse>("/api/forecast"),
  forecasterMetrics: () => getJSON<ForecasterMetrics>("/api/forecaster/metrics"),
  pipelineStatus: () => getJSON<PipelineStatus>("/api/pipeline/status"),
  askQuestion: async (question: string): Promise<string> => {
    const res = await fetch(`${API_BASE}/api/qa`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) throw new Error(`qa failed: ${res.status}`);
    const data = (await res.json()) as { answer: string };
    return data.answer;
  },
};
