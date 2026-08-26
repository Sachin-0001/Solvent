"""
Tier 1: exact match. Pure code, zero LLM calls.

Ledger carries the gross transaction amount plus the fee, GST-on-fee, and any
refund amount the merchant's own system recorded at transaction time; the bank
sees only the net-of-all-that settled amount. So "exact" doesn't mean amount
equality — it means the bank amount equals the ledger's expected net
(amount - fee - tax_on_fee - refund_amount) within a tight tolerance, and the
settlement timestamp falls within a tight same-day-ish window.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.ingestion.base import Transaction

AMOUNT_TOL_ABS = 5.0  # rupees
AMOUNT_TOL_PCT = 0.015  # 1.5% of ledger amount
TIMESTAMP_TOL_HOURS = 6


@dataclass
class MatchResult:
    ledger_row_id: str
    bank_row_id: str
    order_id: str | None
    tier: str  # "exact" | "fuzzy" | "llm"
    amount_diff: float
    timestamp_diff_hours: float
    explanation: str | None = None


def _group_by_order_id(transactions: list[Transaction]) -> dict[str, list[Transaction]]:
    groups: dict[str, list[Transaction]] = {}
    for t in transactions:
        groups.setdefault(t.order_id or "", []).append(t)
    return groups


def _hours_between(a: str, b: str) -> float:
    return abs((datetime.fromisoformat(a) - datetime.fromisoformat(b)).total_seconds()) / 3600


def expected_net(ledger_txn: Transaction) -> float:
    """Amount the bank should show for this ledger row, net of fee/GST/refund."""
    fee = ledger_txn.fee or 0.0
    tax_on_fee = ledger_txn.raw.get("tax_on_fee", 0.0) or 0.0
    refund_amount = ledger_txn.raw.get("refund_amount", 0.0) or 0.0
    return ledger_txn.amount - fee - tax_on_fee - refund_amount


def exact_match(
    ledger_txns: list[Transaction], bank_txns: list[Transaction]
) -> tuple[list[MatchResult], list[Transaction], list[Transaction]]:
    ledger_by_order = _group_by_order_id(ledger_txns)
    bank_by_order = _group_by_order_id(bank_txns)

    matches: list[MatchResult] = []
    matched_ledger_ids: set[str] = set()
    matched_bank_ids: set[str] = set()

    for order_id, ledger_group in ledger_by_order.items():
        bank_group = bank_by_order.get(order_id, [])
        if len(ledger_group) != 1 or len(bank_group) != 1:
            continue  # ambiguous group sizes (missing/duplicate) go to fuzzy tier

        l, b = ledger_group[0], bank_group[0]

        amount_diff = abs(b.amount - expected_net(l))
        tol = max(AMOUNT_TOL_ABS, AMOUNT_TOL_PCT * l.amount)
        time_diff = _hours_between(b.created_at, l.created_at)

        if amount_diff <= tol and time_diff <= TIMESTAMP_TOL_HOURS:
            matches.append(
                MatchResult(l.source_id, b.source_id, order_id, "exact", amount_diff, time_diff)
            )
            matched_ledger_ids.add(l.source_id)
            matched_bank_ids.add(b.source_id)

    remaining_ledger = [t for t in ledger_txns if t.source_id not in matched_ledger_ids]
    remaining_bank = [t for t in bank_txns if t.source_id not in matched_bank_ids]
    return matches, remaining_ledger, remaining_bank
