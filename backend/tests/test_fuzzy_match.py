"""
Fuzzy-match tier: widened tolerance bands plus greedy pairing across
group-size mismatches (duplicate/missing injection). Pure code, deterministic.
"""

from __future__ import annotations

from backend.ingestion.base import Transaction
from backend.reconciliation.fuzzy_match import fuzzy_match


def _ledger_txn(order_id="order_1", amount=1000.0, created_at="2025-06-01T10:00:00", fee=20.0, source_id="LEDG00001"):
    return Transaction(
        source="internal_ledger",
        source_id=source_id,
        order_id=order_id,
        amount=amount,
        currency="INR",
        method="card",
        status="settled",
        fee=fee,
        tax_on_fee=0.0,
        settled_at=None,
        created_at=created_at,
        raw={"tax_on_fee": 0.0, "refund_amount": 0.0},
    )


def _bank_txn(order_id="order_1", amount=980.0, created_at="2025-06-01T10:00:00", source_id="BANK00001"):
    return Transaction(
        source="bank_statement",
        source_id=source_id,
        order_id=order_id,
        amount=amount,
        currency="INR",
        method=None,
        status="credited",
        fee=None,
        tax_on_fee=None,
        settled_at=created_at,
        created_at=created_at,
        raw={},
    )


def test_fuzzy_match_absorbs_rounding_drift_beyond_exact_tolerance():
    # Expected net = 1000 - 20 = 980. Off by 25 -> beyond exact match's tolerance
    # (max(5, 1.5%) = 15) but within fuzzy's (max(30, 8%) = 80).
    ledger = [_ledger_txn(amount=1000.0, fee=20.0)]
    bank = [_bank_txn(amount=980.0 - 25)]

    matches, rem_ledger, rem_bank = fuzzy_match(ledger, bank)

    assert len(matches) == 1
    assert matches[0].tier == "fuzzy"
    assert rem_ledger == []
    assert rem_bank == []


def test_fuzzy_match_rejects_gap_beyond_widened_tolerance():
    ledger = [_ledger_txn(amount=1000.0, fee=20.0)]
    bank = [_bank_txn(amount=980.0 - 200)]  # far beyond fuzzy's 8%/₹30 band

    matches, rem_ledger, rem_bank = fuzzy_match(ledger, bank)

    assert matches == []
    assert len(rem_ledger) == 1
    assert len(rem_bank) == 1


def test_fuzzy_match_greedily_pairs_closest_candidates_in_duplicate_group():
    # Two bank rows for one order_id (duplicate injection); the ledger row
    # should pair with whichever bank row is numerically closer.
    ledger = [_ledger_txn(amount=1000.0, fee=20.0, source_id="LEDG00001")]
    bank = [
        _bank_txn(amount=500.0, source_id="BANK00001"),  # far off
        _bank_txn(amount=979.0, source_id="BANK00002"),  # close to expected net 980
    ]

    matches, rem_ledger, rem_bank = fuzzy_match(ledger, bank)

    assert len(matches) == 1
    assert matches[0].bank_row_id == "BANK00002"
    assert rem_ledger == []
    assert [b.source_id for b in rem_bank] == ["BANK00001"]


def test_fuzzy_match_leaves_unmatched_side_untouched_when_no_candidate():
    ledger = [_ledger_txn(order_id="order_1")]
    bank = [_bank_txn(order_id="order_2")]  # no shared order_id at all

    matches, rem_ledger, rem_bank = fuzzy_match(ledger, bank)

    assert matches == []
    assert len(rem_ledger) == 1
    assert len(rem_bank) == 1
