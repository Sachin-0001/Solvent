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

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  reconciliationSummary: () => getJSON<ReconciliationSummary>("/api/reconciliation/summary"),
  reconciliationExceptions: () =>
    getJSON<ReconciliationException[]>("/api/reconciliation/exceptions"),
  taxSummary: () => getJSON<TaxSummary>("/api/tax/summary"),
  forecast: () => getJSON<ForecastResponse>("/api/forecast"),
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
