"""
Track B: the live capability layer (CLAUDE.md sections 3-4) — a merchant's own
data instead of the Track A synthetic demo. Two ingestion sources feed the
exact same reconciliation/tax-matcher/forecaster/QA functions Track A uses
(backend/reconciliation/*, backend/tax_matcher/*, backend/forecaster/predict.py,
backend/qa_agent/agent.py) — nothing in those modules changes; only what
builds their input does.

Deliberately NOT persisted to Postgres (unlike Track A's full-refresh design):
this is one merchant's live/uploaded data for one session, not the demo
dataset every downstream stage is validated against. Results are computed
in-memory and returned directly in the API response; the frontend holds them
in React state for the session. Track B's QA reuse (backend/api.py's
/api/track-b/qa) calls the same answer_question() Track A uses, which
persists embeddings for whatever records it's given (qa_agent/embeddings.py,
keyed by txn_id) — that's a genuine, acknowledged exception to "not
persisted": Track B txn_ids are prefixed with a random per-session id (see
session_prefix below) specifically so two different uploads never collide
under the same txn_id and serve each other's stale embedding text, the same
bug class fixed in run_ingestion.py for Track A. The tradeoff is that these
embedding rows accumulate in Postgres across Track B sessions with nothing to
prune them — acceptable for a demo-scale system, called out here rather than
silently left as a smaller version of the same problem.

Two entry points:
  - run_from_csv(ledger_csv, bank_csv): the merchant uploads both a ledger and
    a bank-statement CSV. Both sides exist, so full reconciliation (exact ->
    fuzzy -> LLM exception) runs exactly like Track A.
  - run_from_razorpay(key_id, key_secret): the merchant connects their own
    Razorpay account. Razorpay's Payments/Settlements API is already the
    merchant's authoritative source for what happened to a payment — there's
    no second, independent ledger to cross-check it against, so
    reconciliation (which exists specifically to catch drift between two
    independent records) genuinely doesn't apply here. This is reported
    honestly as "not applicable", not silently skipped.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from backend.ingestion.base import Transaction
from backend.ingestion.csv_adapter import CSVBankAdapter, CSVFormatError, CSVLedgerAdapter, detect_date_range
from backend.ingestion.razorpay_adapter import RazorpayAdapter
from backend.reconciliation.engine import exceptions_to_dicts, matches_to_dicts
from backend.reconciliation.exact_match import exact_match
from backend.reconciliation.fuzzy_match import fuzzy_match
from backend.reconciliation.llm_exception import llm_exception_pass
from backend.tax_matcher.matcher import classifications_to_dicts, run_tax_matcher


def _ledger_txn_to_dict(t: Transaction, index: int, session_prefix: str) -> dict[str, Any]:
    """Builds the transaction-dict shape tax_matcher/forecaster expect, from a
    single uploaded ledger row. merchant_category and had_dispute_flag aren't
    knowable from a ledger/bank CSV at all (they're business-classification
    fields, not reconciliation data) — defaulted to "unknown"/False rather
    than guessed; the one-hot encoder handles an unseen category via
    handle_unknown="ignore" (see features.py), so this degrades gracefully
    rather than erroring. gst_on_fee_flag is inferred from tax_on_fee > 0
    since a CSV export won't carry that flag explicitly — an honest heuristic,
    not the same ground-truth-certain field Track A's synthetic data has."""
    created_dt = datetime.fromisoformat(t.created_at)
    refund_amount = t.raw.get("refund_amount", 0.0) or 0.0
    tax_on_fee = t.raw.get("tax_on_fee", 0.0) or 0.0
    fee_amount = t.fee or 0.0
    return {
        "txn_id": f"{session_prefix}{t.source_id}",
        "order_id": t.order_id,
        "txn_amount": t.amount,
        "payment_method": t.method or "unknown",
        "created_at": t.created_at,
        "day_of_week": created_dt.weekday(),
        "is_weekend_or_holiday": created_dt.weekday() >= 5,
        "merchant_category": "unknown",
        "had_dispute_flag": False,
        "had_refund": refund_amount > 0,
        "refund_amount": refund_amount,
        "gst_on_fee_flag": tax_on_fee > 0,
        "fee_amount": fee_amount,
        "fee_amount_pending": False,  # CSV can't distinguish "0" from "not provided" post-default
        "tax_on_fee": tax_on_fee,
        "days_to_settle": None,
        "status": t.status,
    }


def _razorpay_txn_to_dict(t: Transaction, session_prefix: str) -> dict[str, Any]:
    """Same shape, built from a live RazorpayAdapter Transaction. Unlike CSV,
    a genuinely-pending fee is directly knowable here (t.fee is None when the
    payment hasn't been swept into a settlement yet — see
    razorpay_adapter.py's own docstring), so fee_amount_pending is a real
    signal, not always False."""
    created_dt = datetime.fromisoformat(t.created_at) if t.created_at else datetime.now()
    payment = t.raw.get("payment", {}) if isinstance(t.raw, dict) else {}
    refund_amount = (payment.get("amount_refunded") or 0) / 100
    tax_on_fee = t.tax_on_fee or 0.0
    return {
        "txn_id": f"{session_prefix}{t.source_id}",
        "order_id": t.order_id,
        "txn_amount": t.amount,
        "payment_method": t.method or "unknown",
        "created_at": t.created_at or created_dt.isoformat(),
        "day_of_week": created_dt.weekday(),
        "is_weekend_or_holiday": created_dt.weekday() >= 5,
        "merchant_category": "unknown",
        "had_dispute_flag": False,
        "had_refund": refund_amount > 0,
        "refund_amount": refund_amount,
        "gst_on_fee_flag": tax_on_fee > 0,
        "fee_amount": t.fee if t.fee is not None else 0.0,
        "fee_amount_pending": t.fee is None,
        "tax_on_fee": tax_on_fee,
        "days_to_settle": None,
        "status": t.status,
    }


def _tax_and_forecast(txn_dicts: list[dict[str, Any]]) -> dict[str, Any]:
    tax_result = run_tax_matcher(txn_dicts)
    classifications = classifications_to_dicts(tax_result["classifications"])
    category_counts: dict[str, int] = {}
    for c in classifications:
        category_counts[c["category"]] = category_counts.get(c["category"], 0) + 1

    forecast_days: list[dict[str, Any]] | None = None
    forecast_error: str | None = None
    if txn_dicts:
        try:
            from backend.forecaster.predict import forecast_daily_cashflow

            forecast_days = forecast_daily_cashflow(txn_dicts)
        except Exception as e:  # noqa: BLE001 - surfaced to the user as an honest message, not a 500
            forecast_error = f"{e.__class__.__name__}: {e}"

    return {
        "tax_classification": {
            "total": len(classifications),
            "category_counts": category_counts,
            "resolved_by_rules": tax_result["rule_count"],
            "resolved_by_llm": tax_result["llm_count"],
            "unresolved": tax_result["exception_count"],
        },
        "forecast": {"days": forecast_days, "error": forecast_error},
        "classifications": classifications,
    }


def run_from_csv(ledger_csv: str, bank_csv: str) -> dict[str, Any]:
    session_prefix = f"TB{uuid.uuid4().hex[:8]}_"
    ledger_txns = CSVLedgerAdapter(ledger_csv).fetch()
    bank_txns = CSVBankAdapter(bank_csv).fetch()

    exact_matches, rem_ledger, rem_bank = exact_match(ledger_txns, bank_txns)
    fuzzy_matches, rem_ledger, rem_bank = fuzzy_match(rem_ledger, rem_bank)
    llm_matches, exceptions = llm_exception_pass(rem_ledger, rem_bank)
    all_matches = exact_matches + fuzzy_matches + llm_matches

    txn_dicts = [_ledger_txn_to_dict(t, i, session_prefix) for i, t in enumerate(ledger_txns)]
    matched_ledger_ids = {m.ledger_row_id for m in all_matches}
    for t, d in zip(ledger_txns, txn_dicts):
        d["reconciliation_status"] = "matched" if t.source_id in matched_ledger_ids else "exception"

    result = _tax_and_forecast(txn_dicts)
    result.update(
        {
            "source": "csv_upload",
            "date_range": detect_date_range(ledger_txns + bank_txns),
            "reconciliation": {
                "total_ledger_rows": len(ledger_txns),
                "total_bank_rows": len(bank_txns),
                "matched": len(all_matches),
                "tier_counts": {
                    "exact": len(exact_matches),
                    "fuzzy": len(fuzzy_matches),
                    "llm": len(llm_matches),
                },
                "exception_count": len(exceptions),
                "note": "No ground truth for uploaded data, so this reports match "
                "counts only — no precision/recall (those require knowing the "
                "true pairing in advance, which Track A's synthetic ground truth "
                "provides and real merchant data cannot).",
            },
            "exceptions": exceptions_to_dicts(exceptions),
            "records": txn_dicts,
        }
    )
    return result


def run_from_razorpay(key_id: str, key_secret: str) -> dict[str, Any]:
    # key_id/key_secret live only in this function's locals for the duration
    # of one request — never logged, never written to a file or the database,
    # never included in the returned dict.
    session_prefix = f"TB{uuid.uuid4().hex[:8]}_"
    adapter = RazorpayAdapter(key_id=key_id, key_secret=key_secret)
    transactions = [t for t in adapter.fetch(order_count=100) if t.created_at]

    txn_dicts = [_razorpay_txn_to_dict(t, session_prefix) for t in transactions]
    for d in txn_dicts:
        d["reconciliation_status"] = "not_applicable"

    result = _tax_and_forecast(txn_dicts)
    result.update(
        {
            "source": "razorpay_connect",
            "date_range": detect_date_range(transactions),
            "reconciliation": {
                "note": "Not applicable: Razorpay's own Payments/Settlements API is "
                "already the merchant's authoritative record. Reconciliation exists "
                "to catch drift between two *independent* sources (a ledger and a "
                "bank statement) — there is no second source here to cross-check "
                "against, so this is honestly reported as not applicable rather "
                "than a fabricated 100% match rate.",
            },
            "exceptions": [],
            "records": txn_dicts,
            "transactions_fetched": len(transactions),
        }
    )
    return result


__all__ = ["run_from_csv", "run_from_razorpay", "CSVFormatError"]
