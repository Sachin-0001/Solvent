"""
Rule-based GST-treatment classifier. Pure code, zero LLM calls, zero ML — this is
a deterministic decision tree over fields the reconciled transaction record
already carries, not a trained classifier of any kind (no Random Forest, no
XGBoost — see CLAUDE.md).

Categories, in priority order:
  1. refund_credit_note — a refund occurred; the refunded portion needs a
     credit note regardless of size, so this takes precedence over everything.
  2. exempt              — gst_on_fee_flag is False (the transaction/merchant
     falls under a GST-exempt fee arrangement).
  3. gst_on_fee          — a nonzero gateway fee was charged and GST applies
     to it (the common case for card/netbanking/wallet).
  4. taxable_sale        — the default: a standard sale with standard GST,
     no special adjustment needed (typically zero-fee UPI transactions).

Returns None (unresolved) only when a required field is missing or malformed —
that's the genuine, honest trigger for the LLM fallback tier, not manufactured
ambiguity in the business logic itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REQUIRED_FIELDS = ("had_refund", "gst_on_fee_flag", "fee_amount")

VALID_CATEGORIES = {"refund_credit_note", "exempt", "gst_on_fee", "taxable_sale"}


@dataclass
class TaxClassification:
    txn_id: str
    category: str
    method: str  # "rule" | "llm"
    reasoning: str


def classify_by_rules(txn: dict[str, Any]) -> TaxClassification | None:
    if any(txn.get(f) is None for f in REQUIRED_FIELDS):
        return None

    had_refund = bool(txn["had_refund"])
    gst_on_fee_flag = bool(txn["gst_on_fee_flag"])
    fee_amount = txn["fee_amount"]

    if not isinstance(fee_amount, (int, float)):
        return None

    if had_refund:
        return TaxClassification(
            txn["txn_id"], "refund_credit_note", "rule",
            "had_refund=True — refunded amount requires a credit-note adjustment.",
        )
    if not gst_on_fee_flag:
        return TaxClassification(
            txn["txn_id"], "exempt", "rule",
            "gst_on_fee_flag=False — this transaction's fee arrangement is GST-exempt.",
        )
    if fee_amount > 0:
        return TaxClassification(
            txn["txn_id"], "gst_on_fee", "rule",
            f"Nonzero gateway fee ({fee_amount}) with GST applicable — classified as GST-on-fee.",
        )
    return TaxClassification(
        txn["txn_id"], "taxable_sale", "rule",
        "No refund, no fee, GST-on-fee not applicable — standard taxable sale.",
    )
