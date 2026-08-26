"""
Tier 2: fuzzy match. Still pure code, zero LLM calls.

Widens the amount and timestamp tolerance bands from exact match to absorb
rounding drift and timestamp drift (the two injected mismatch kinds designed to
survive exact match but not be genuinely ambiguous), and handles group-size
mismatches from duplicate injection (2 ledger rows vs 1 bank row, or vice versa)
by greedily assigning the closest-scoring pair within each order_id group.

Anything left over after this tier — refunds whose amount gap exceeds even this
band, and true group-size mismatches with no candidate at all — is genuinely
ambiguous and goes to the LLM exception tier.
"""

from __future__ import annotations

from backend.ingestion.base import Transaction
from backend.reconciliation.exact_match import (
    MatchResult,
    _group_by_order_id,
    _hours_between,
    expected_net,
)

AMOUNT_TOL_ABS = 30.0
AMOUNT_TOL_PCT = 0.08
TIMESTAMP_TOL_HOURS = 96


def fuzzy_match(
    remaining_ledger: list[Transaction], remaining_bank: list[Transaction]
) -> tuple[list[MatchResult], list[Transaction], list[Transaction]]:
    ledger_by_order = _group_by_order_id(remaining_ledger)
    bank_by_order = _group_by_order_id(remaining_bank)
    all_order_ids = set(ledger_by_order) | set(bank_by_order)

    matches: list[MatchResult] = []
    matched_ledger_ids: set[str] = set()
    matched_bank_ids: set[str] = set()

    for order_id in all_order_ids:
        lg = ledger_by_order.get(order_id, [])
        bg = bank_by_order.get(order_id, [])
        if not lg or not bg:
            continue  # no candidate at all on one side -> LLM exception tier

        candidates = []
        for l in lg:
            net = expected_net(l)
            tol = max(AMOUNT_TOL_ABS, AMOUNT_TOL_PCT * l.amount)
            for b in bg:
                amount_diff = abs(b.amount - net)
                time_diff = _hours_between(b.created_at, l.created_at)
                if amount_diff <= tol and time_diff <= TIMESTAMP_TOL_HOURS:
                    score = (amount_diff / max(l.amount, 1)) + (time_diff / TIMESTAMP_TOL_HOURS)
                    candidates.append((score, l, b, amount_diff, time_diff))

        candidates.sort(key=lambda c: c[0])
        used_l: set[str] = set()
        used_b: set[str] = set()
        for _, l, b, amount_diff, time_diff in candidates:
            if l.source_id in used_l or b.source_id in used_b:
                continue
            matches.append(
                MatchResult(l.source_id, b.source_id, order_id, "fuzzy", amount_diff, time_diff)
            )
            used_l.add(l.source_id)
            used_b.add(b.source_id)
            matched_ledger_ids.add(l.source_id)
            matched_bank_ids.add(b.source_id)

    remaining_ledger2 = [t for t in remaining_ledger if t.source_id not in matched_ledger_ids]
    remaining_bank2 = [t for t in remaining_bank if t.source_id not in matched_bank_ids]
    return matches, remaining_ledger2, remaining_bank2
