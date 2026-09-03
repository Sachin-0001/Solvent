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

export type ReviewDecision = "approved_match" | "written_off" | "manually_paired";

export interface ReconciliationReview {
  id: number;
  row_id: string;
  side: string;
  order_id: string | null;
  decision: ReviewDecision;
  paired_row_id: string | null;
  note: string | null;
  reviewer: string | null;
  decided_at: string;
}

export interface ReviewCandidate {
  row_id: string;
  order_id: string;
  amount: number;
  timestamp: string;
  narration?: string | null;
}

export interface ReviewQueueItem extends ReconciliationException {
  source_row: ReviewCandidate | null;
  candidates: ReviewCandidate[];
  review: ReconciliationReview | null;
}

export interface ReviewQueueResponse {
  total: number;
  pending: number;
  resolved: number;
  items: ReviewQueueItem[];
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

export interface ToolCallTrace {
  name: string;
  arguments: Record<string, unknown>;
  status: "success" | "error";
  result_summary: string;
  duration_ms: number;
}

export interface QAResponse {
  answer: string;
  trace: ToolCallTrace[];
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

export interface CombinedModelBReport {
  label: string;
  target: string;
  n_test: number;
  mae: number;
  mape_pct: number;
}

export interface GmvModelReport {
  label: string;
  target: string;
  method: string;
  n_train: number;
  n_test: number;
  mae: number;
  rmse: number;
  naive_mae: number;
  improvement_pct: number | null;
  model_path: string;
}

export interface ForecasterMetrics {
  model_a: ForecasterModelReport | null;
  model_b_fee: ForecasterModelReport | null;
  model_b_refund: ForecasterModelReport | null;
  model_b_combined: CombinedModelBReport | null;
  gmv: GmvModelReport | null;
}

export interface GmvForecast {
  value: number;
  method: string;
  model: string | null;
  forecast_date: string | null;
  based_on_date: string | null;
}

export interface CashPositionMethod {
  method: string;
  model: string | null;
  based_on_date: string | null;
}

export interface CashPosition {
  current_cash: number;
  expected_settlement: number;
  expected_refunds: number;
  expected_net_cash_flow: number;
  projected_cash: number;
  forecast_date: string | null;
  forecast_method: {
    settlement: CashPositionMethod;
    refunds: CashPositionMethod;
  };
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

export interface TrackBRecord {
  txn_id: string;
  order_id: string | null;
  txn_amount: number;
  payment_method: string;
  created_at: string;
  had_refund: boolean;
  refund_amount: number;
  status: string;
  reconciliation_status: string;
}

export interface TrackBClassification {
  txn_id: string;
  category: string;
  method: string;
  reasoning: string;
}

export interface TrackBException {
  row_id: string;
  side: string;
  order_id: string | null;
  reason: string;
  explanation: string;
}

export interface TrackBResult {
  source: "csv_upload" | "razorpay_connect";
  date_range: { start: string; end: string } | null;
  reconciliation: {
    note: string;
    total_ledger_rows?: number;
    total_bank_rows?: number;
    matched?: number;
    tier_counts?: Record<string, number>;
    exception_count?: number;
  };
  exceptions: TrackBException[];
  tax_classification: {
    total: number;
    category_counts: Record<string, number>;
    resolved_by_rules: number;
    resolved_by_llm: number;
    unresolved: number;
  };
  classifications: TrackBClassification[];
  forecast: { days: ForecastDay[] | null; error: string | null };
  records: TrackBRecord[];
  transactions_fetched?: number;
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
  reviewQueue: (status?: "pending" | "resolved") =>
    getJSON<ReviewQueueResponse>(
      `/api/reconciliation/review-queue${status ? `?status=${status}` : ""}`
    ),
  submitReview: async (body: {
    row_id: string;
    side: string;
    decision: ReviewDecision;
    order_id?: string | null;
    paired_row_id?: string | null;
    note?: string | null;
    reviewer?: string | null;
  }): Promise<ReconciliationReview> => {
    const res = await fetch(`${API_BASE}/api/reconciliation/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail ?? `review failed: ${res.status}`);
    }
    return res.json() as Promise<ReconciliationReview>;
  },
  reopenReview: async (rowId: string, side: string): Promise<void> => {
    const params = new URLSearchParams({ row_id: rowId, side });
    const res = await fetch(`${API_BASE}/api/reconciliation/review?${params}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error(`reopen failed: ${res.status}`);
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
  forecastGmv: () => getJSON<GmvForecast>("/api/forecast/gmv"),
  cashPosition: (currentCash?: number) => {
    const qs = currentCash !== undefined ? `?current_cash=${currentCash}` : "";
    return getJSON<CashPosition>(`/api/cash-position${qs}`);
  },
  pipelineStatus: () => getJSON<PipelineStatus>("/api/pipeline/status"),
  askQuestion: async (question: string): Promise<QAResponse> => {
    const res = await fetch(`${API_BASE}/api/qa`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) throw new Error(`qa failed: ${res.status}`);
    return res.json() as Promise<QAResponse>;
  },
  trackBConnect: async (keyId: string, keySecret: string): Promise<TrackBResult> => {
    const res = await fetch(`${API_BASE}/api/track-b/connect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key_id: keyId, key_secret: keySecret }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail ?? `connect failed: ${res.status}`);
    }
    return res.json() as Promise<TrackBResult>;
  },
  trackBUpload: async (ledgerFile: File, bankFile: File): Promise<TrackBResult> => {
    const form = new FormData();
    form.append("ledger_file", ledgerFile);
    form.append("bank_file", bankFile);
    const res = await fetch(`${API_BASE}/api/track-b/upload`, { method: "POST", body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail ?? `upload failed: ${res.status}`);
    }
    return res.json() as Promise<TrackBResult>;
  },
  trackBAsk: async (question: string, records: TrackBRecord[]): Promise<QAResponse> => {
    const res = await fetch(`${API_BASE}/api/track-b/qa`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, records }),
    });
    if (!res.ok) throw new Error(`track-b qa failed: ${res.status}`);
    return res.json() as Promise<QAResponse>;
  },
};
