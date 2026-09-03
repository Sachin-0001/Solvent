"""
Deterministic tools the Q&A agent (backend/qa_agent/agent.py) exposes to Groq
via its function-calling API. Every tool is plain Python over data this
codebase already has — no tool invents data, and no tool asks the LLM to do
arithmetic. The LLM's job is deciding *which* tool(s) answer a question and
in what order, then narrating the results — never producing the numbers itself.

Tool -> real data source:
  search_payments          base_transactions (Postgres, or Track B records)
  search_settlements       base_transactions filtered to status == "settled"
  search_invoices          tax_classifications — the closest real proxy for
                            "invoice" data this system has (GST treatment per
                            transaction line). There is no separate invoice
                            table; this is an honest reframing, not fabricated
                            data, and the tool's own description says so.
  find_relation             joins base_transactions + reconciliation
                            matches/exceptions + tax_classifications (+
                            ledger/bank rows when available) for one order_id
                            or txn_id — the real cross-source relationship
                            graph this system has.
  generate_audit_report     aggregates reconciliation/tax/forecast/cash-
                            position stats into one structured JSON report —
                            no LLM call inside it; the agent's outer Groq call
                            narrates the returned numbers.

Every tool function returns a plain JSON-serializable dict/list — that's
what's fed back to Groq as the tool result.
"""

from __future__ import annotations

import re
from typing import Any

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_payments",
            "description": (
                "Search transaction/payment records by order_id, txn_id, payment "
                "method, dispute flag, or refund flag. Use this for questions about "
                "individual payments — amounts, methods, disputes, refunds."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Exact order_id to look up."},
                    "txn_id": {"type": "string", "description": "Exact txn_id to look up."},
                    "payment_method": {
                        "type": "string",
                        "description": "Filter by payment method, e.g. card, upi, netbanking, wallet.",
                    },
                    "had_refund": {"type": "boolean", "description": "Filter to only refunded (true) or non-refunded (false) transactions."},
                    "had_dispute_flag": {"type": "boolean", "description": "Filter to only disputed (true) or non-disputed (false) transactions."},
                    "limit": {"type": "integer", "description": "Max records to return (default 10)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_settlements",
            "description": (
                "Search settled transactions (status == 'settled') by order_id/txn_id "
                "or settlement date range. Use this for questions about when money "
                "settled or how much settled."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "txn_id": {"type": "string"},
                    "settled_after": {"type": "string", "description": "ISO date, e.g. 2025-06-01. Only settlements on/after this date."},
                    "settled_before": {"type": "string", "description": "ISO date. Only settlements on/before this date."},
                    "limit": {"type": "integer", "description": "Max records to return (default 10)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_invoices",
            "description": (
                "Search GST/tax-treatment classifications for transactions (the "
                "closest thing this system has to an invoice line — there is no "
                "separate invoice document store, so this returns each "
                "transaction's tax category and reasoning). Use this for questions "
                "about GST category, exemptions, or credit notes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "txn_id": {"type": "string"},
                    "category": {
                        "type": "string",
                        "description": "One of: refund_credit_note, exempt, gst_on_fee, taxable_sale, unresolved.",
                    },
                    "limit": {"type": "integer", "description": "Max records to return (default 10)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_relation",
            "description": (
                "Given one order_id or txn_id, return everything linked to it: the "
                "base transaction, its reconciliation match or exception (with "
                "ledger/bank row detail when available), and its tax classification. "
                "Use this when the merchant asks 'what happened to' a specific "
                "order/transaction, or how its pieces relate to each other."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "txn_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_audit_report",
            "description": (
                "Produce a structured summary covering reconciliation health "
                "(match rate, precision/recall, exceptions), tax classification "
                "breakdown, forecaster metrics, and current cash position. Use "
                "this for broad 'how are we doing' / 'give me an audit summary' "
                "questions rather than fetching each piece separately."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _apply_limit(rows: list[dict], limit: int | None) -> list[dict]:
    return rows[: (limit or 10)]


def search_payments(
    records: list[dict[str, Any]],
    order_id: str | None = None,
    txn_id: str | None = None,
    payment_method: str | None = None,
    had_refund: bool | None = None,
    had_dispute_flag: bool | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    rows = records
    if order_id:
        rows = [r for r in rows if r.get("order_id") == order_id]
    if txn_id:
        rows = [r for r in rows if r.get("txn_id") == txn_id]
    if payment_method:
        rows = [r for r in rows if r.get("payment_method") == payment_method]
    if had_refund is not None:
        rows = [r for r in rows if bool(r.get("had_refund")) == had_refund]
    if had_dispute_flag is not None:
        rows = [r for r in rows if bool(r.get("had_dispute_flag")) == had_dispute_flag]

    matched = _apply_limit(rows, limit)
    return {
        "total_matched": len(rows),
        "returned": len(matched),
        "records": [
            {
                "txn_id": r.get("txn_id"),
                "order_id": r.get("order_id"),
                "txn_amount": r.get("txn_amount"),
                "payment_method": r.get("payment_method"),
                "created_at": r.get("created_at"),
                "status": r.get("status"),
                "had_refund": r.get("had_refund"),
                "refund_amount": r.get("refund_amount"),
                "had_dispute_flag": r.get("had_dispute_flag"),
                "reconciliation_status": r.get("reconciliation_status"),
            }
            for r in matched
        ],
    }


def search_settlements(
    records: list[dict[str, Any]],
    order_id: str | None = None,
    txn_id: str | None = None,
    settled_after: str | None = None,
    settled_before: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    rows = [r for r in records if r.get("status") == "settled" and r.get("settled_at")]
    if order_id:
        rows = [r for r in rows if r.get("order_id") == order_id]
    if txn_id:
        rows = [r for r in rows if r.get("txn_id") == txn_id]
    if settled_after:
        rows = [r for r in rows if str(r["settled_at"]) >= settled_after]
    if settled_before:
        rows = [r for r in rows if str(r["settled_at"]) <= settled_before]

    matched = _apply_limit(rows, limit)
    total_amount = sum((r.get("txn_amount") or 0.0) for r in rows)
    return {
        "total_matched": len(rows),
        "returned": len(matched),
        "total_settlement_amount": round(total_amount, 2),
        "records": [
            {
                "txn_id": r.get("txn_id"),
                "order_id": r.get("order_id"),
                "txn_amount": r.get("txn_amount"),
                "settled_at": r.get("settled_at"),
                "days_to_settle": r.get("days_to_settle"),
                "fee_amount": r.get("fee_amount"),
                "tax_on_fee": r.get("tax_on_fee"),
            }
            for r in matched
        ],
    }


def search_invoices(
    records: list[dict[str, Any]],
    txn_id: str | None = None,
    category: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    rows = [r for r in records if r.get("tax_category")]
    if txn_id:
        rows = [r for r in rows if r.get("txn_id") == txn_id]
    if category:
        rows = [r for r in rows if r.get("tax_category") == category]

    matched = _apply_limit(rows, limit)
    return {
        "note": (
            "This system has no separate invoice store — these are per-transaction "
            "GST/tax-treatment classifications, the closest real proxy for an "
            "invoice line."
        ),
        "total_matched": len(rows),
        "returned": len(matched),
        "records": [
            {
                "txn_id": r.get("txn_id"),
                "order_id": r.get("order_id"),
                "txn_amount": r.get("txn_amount"),
                "tax_category": r.get("tax_category"),
                "tax_reasoning": r.get("tax_reasoning"),
            }
            for r in matched
        ],
    }


def find_relation(
    records: list[dict[str, Any]],
    order_id: str | None = None,
    txn_id: str | None = None,
) -> dict[str, Any]:
    if not order_id and not txn_id:
        return {"error": "Provide order_id or txn_id."}

    matches = [
        r for r in records
        if (order_id and r.get("order_id") == order_id) or (txn_id and r.get("txn_id") == txn_id)
    ]
    if not matches:
        return {"found": False, "order_id": order_id, "txn_id": txn_id}

    record = matches[0]
    relation: dict[str, Any] = {
        "found": True,
        "transaction": {
            "txn_id": record.get("txn_id"),
            "order_id": record.get("order_id"),
            "txn_amount": record.get("txn_amount"),
            "payment_method": record.get("payment_method"),
            "created_at": record.get("created_at"),
            "status": record.get("status"),
        },
        "reconciliation": {
            "status": record.get("reconciliation_status"),
            "tier": record.get("reconciliation_tier"),
            "exception_reasons": record.get("reconciliation_reasons"),
        },
        "tax_classification": {
            "category": record.get("tax_category"),
            "reasoning": record.get("tax_reasoning"),
        },
    }
    if record.get("had_refund"):
        relation["refund"] = {"amount": record.get("refund_amount")}
    if record.get("had_dispute_flag"):
        relation["dispute"] = True
    return relation


_ORDER_OR_TXN_ID = re.compile(r"\b(?:order_[A-Za-z0-9_]+|TXN\d+)\b")


def generate_audit_report(
    records: list[dict[str, Any]],
    reconciliation_summary: dict[str, Any] | None = None,
    tax_summary: dict[str, Any] | None = None,
    cash_position: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure aggregation over what's already been computed elsewhere
    (reconciliation validation, tax breakdown, cash position) plus a quick
    pass over `records` — never re-derives reconciliation/tax logic itself,
    just summarizes results already produced by those pipelines."""
    total = len(records)
    reconciled = sum(1 for r in records if r.get("reconciliation_status") == "matched")
    exceptions = sum(1 for r in records if r.get("reconciliation_status") == "exception")
    disputed = sum(1 for r in records if r.get("had_dispute_flag"))
    refunded = sum(1 for r in records if r.get("had_refund"))
    total_refund_amount = round(sum((r.get("refund_amount") or 0.0) for r in records), 2)

    tax_breakdown: dict[str, int] = {}
    for r in records:
        cat = r.get("tax_category") or "unclassified"
        tax_breakdown[cat] = tax_breakdown.get(cat, 0) + 1

    report: dict[str, Any] = {
        "total_transactions": total,
        "reconciliation": {
            "reconciled": reconciled,
            "exceptions": exceptions,
            "match_rate_pct": round(100 * reconciled / total, 2) if total else 0.0,
            **({"validated_summary": reconciliation_summary} if reconciliation_summary else {}),
        },
        "tax_classification_breakdown": tax_breakdown,
        **({"tax_summary": tax_summary} if tax_summary else {}),
        "disputed_count": disputed,
        "refunded_count": refunded,
        "total_refund_amount": total_refund_amount,
    }
    if cash_position:
        report["cash_position"] = cash_position
    return report


__all__ = [
    "TOOL_SCHEMAS",
    "search_payments",
    "search_settlements",
    "search_invoices",
    "find_relation",
    "generate_audit_report",
]
