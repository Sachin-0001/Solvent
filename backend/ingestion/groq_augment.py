"""
Adds realistic free-text narration fields on top of the synthetic ledger and bank
statement rows, via the shared Groq wrapper. This is the only LLM usage in the
ingestion stage — everything else here (base transaction generation, mismatch
injection) is pure code.

Batches rows into groups per call (instead of one call per row) to keep LLM call
volume down, per the project's "minimize LLM calls by design" rule.
"""

from __future__ import annotations

from typing import Any

from backend.llm.groq_client import GroqError, call_groq_json

BATCH_SIZE = 25

LEDGER_SYSTEM = (
    "You are generating realistic internal-ledger narration text for an Indian "
    "payment aggregator merchant's bookkeeping system. Keep entries short, varied, "
    "and businesslike (e.g. 'Settlement credit - Order #ORD1234 via UPI')."
)

BANK_SYSTEM = (
    "You are generating realistic Indian bank statement narration lines for "
    "incoming payment-gateway settlement credits, in the terse abbreviated style "
    "real bank statements use (e.g. 'NEFT-RAZORPAY SETL-ORD1234-UTR9182736450')."
)


def _augment_batch(rows: list[dict[str, Any]], system: str) -> dict[str, str]:
    items = [
        {
            "row_id": r["row_id"],
            "order_id": r["order_id"],
            "amount": r["amount"],
        }
        for r in rows
    ]
    prompt = (
        "For each item below, write one realistic narration string.\n"
        f"Items: {items}\n\n"
        'Respond with a JSON object mapping row_id -> narration string, e.g. '
        '{"LEDG00001": "..."}. Include every row_id exactly once.'
    )
    try:
        result = call_groq_json(prompt, system=system, max_tokens=2048)
        if isinstance(result, dict):
            return {str(k): str(v) for k, v in result.items()}
    except (ValueError, GroqError):
        pass
    return {}


def augment_rows(rows: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    """kind is 'ledger' or 'bank'. Returns rows with a 'narration' field added.
    Falls back to a deterministic template string if the Groq call fails, so
    ingestion never hard-fails on an LLM hiccup."""
    system = LEDGER_SYSTEM if kind == "ledger" else BANK_SYSTEM

    augmented = list(rows)
    for start in range(0, len(augmented), BATCH_SIZE):
        batch = augmented[start : start + BATCH_SIZE]
        narrations = _augment_batch(batch, system)
        for row in batch:
            row["narration"] = narrations.get(
                row["row_id"],
                f"Settlement - Order {row['order_id']} - INR {row['amount']}",
            )
    return augmented
