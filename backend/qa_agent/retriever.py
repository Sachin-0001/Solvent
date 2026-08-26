"""
Builds one unified settlement-record view by joining stage 1-4 outputs (from
Postgres, not flat files), then retrieves the subset relevant to a merchant's
question via local-embedding semantic search — see embeddings.py. An explicit
order/txn ID mention in the question still short-circuits straight to that
record, since that's a strictly better answer than a similarity search when
the merchant already told us exactly what they're asking about.
"""

from __future__ import annotations

import re
from typing import Any

from backend import db
from backend.forecaster.predict import forecast_daily_cashflow, predict_transaction
from backend.qa_agent.embeddings import semantic_search

FORWARD_LOOKING_KEYWORDS = (
    "forecast", "upcoming", "next week", "next 7", "expect", "will i",
    "going to", "future", "projection", "cash flow", "cashflow",
)


def load_settlement_records() -> list[dict[str, Any]]:
    transactions = db.load_base_transactions()
    matches = db.load_reconciliation_matches()
    exceptions = db.load_reconciliation_exceptions()
    tax_classifications = db.load_tax_classifications()

    match_by_order: dict[str, dict] = {m["order_id"]: m for m in matches if m["order_id"]}
    exceptions_by_order: dict[str, list[dict]] = {}
    for e in exceptions:
        exceptions_by_order.setdefault(e["order_id"], []).append(e)
    tax_by_txn = {t["txn_id"]: t for t in tax_classifications}

    records = []
    for txn in transactions:
        record = dict(txn)
        order_id = txn["order_id"]

        if order_id in match_by_order:
            m = match_by_order[order_id]
            record["reconciliation_status"] = "matched"
            record["reconciliation_tier"] = m["tier"]
        elif order_id in exceptions_by_order:
            record["reconciliation_status"] = "exception"
            record["reconciliation_reasons"] = [
                {"reason": e["reason"], "explanation": e["explanation"]}
                for e in exceptions_by_order[order_id]
            ]
        else:
            record["reconciliation_status"] = "no_settlement_data"

        tax = tax_by_txn.get(txn["txn_id"])
        if tax:
            record["tax_category"] = tax["category"]
            record["tax_reasoning"] = tax["reasoning"]

        records.append(record)

    return records


def _extract_order_ids(question: str) -> list[str]:
    return re.findall(r"\b(?:order_[A-Za-z0-9_]+|TXN\d+)\b", question)


def _is_forward_looking(question: str) -> bool:
    lowered = question.lower()
    return any(kw in lowered for kw in FORWARD_LOOKING_KEYWORDS)


def retrieve(question: str, records: list[dict[str, Any]], max_records: int = 15) -> dict[str, Any]:
    """
    Returns a context dict for the Q&A agent: a handful of relevant records
    (explicit id mention takes priority; otherwise semantic search over all
    records), always-on aggregate stats, and forecast output when the
    question is forward-looking.
    """
    ids = _extract_order_ids(question)

    if ids:
        matched_records = [r for r in records if r["order_id"] in ids or r["txn_id"] in ids]
    else:
        matched_records = semantic_search(question, records, top_k=max_records)

    matched_records = matched_records[:max_records]

    # Exact global counts — computed once over all records, not inferred from
    # whatever semantic search happened to retrieve. Count-style questions
    # ("how many disputed transactions") need real aggregates, not a similarity
    # search's top-k, which is a relevance ranking, not an exhaustive filter.
    tax_breakdown: dict[str, int] = {}
    method_breakdown: dict[str, int] = {}
    for r in records:
        cat = r.get("tax_category", "unclassified")
        tax_breakdown[cat] = tax_breakdown.get(cat, 0) + 1
        method = r.get("payment_method", "unknown")
        method_breakdown[method] = method_breakdown.get(method, 0) + 1

    reconciled = sum(1 for r in records if r.get("reconciliation_status") == "matched")
    aggregate_stats = {
        "total_transactions": len(records),
        "reconciled": reconciled,
        "exceptions": sum(1 for r in records if r.get("reconciliation_status") == "exception"),
        "match_rate_pct": round(100 * reconciled / len(records), 2) if records else 0.0,
        "tax_category_breakdown": tax_breakdown,
        "payment_method_breakdown": method_breakdown,
        "disputed_count": sum(1 for r in records if r.get("had_dispute_flag")),
        "refunded_count": sum(1 for r in records if r.get("had_refund")),
        "total_refund_amount": round(sum(r.get("refund_amount") or 0 for r in records), 2),
    }

    forecast = None
    if _is_forward_looking(question):
        forecast = forecast_daily_cashflow(records)

    return {
        "records": matched_records,
        "aggregate_stats": aggregate_stats,
        "forecast": forecast,
    }
