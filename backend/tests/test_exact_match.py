"""
Exact-match tier: pure code, deterministic, no external dependencies — the
easiest and most valuable piece to pin down with unit tests (flagged as a
real gap when the project had zero automated tests).
"""

from __future__ import annotations

from backend.ingestion.base import Transaction
from backend.reconciliation.exact_match import exact_match


def _ledger_txn(order_id="order_1", amount=1000.0, created_at="2025-06-01T10:00:00", fee=20.0, tax_on_fee=3.6, refund_amount=0.0, source_id="LEDG00001"):
    return Transaction(
        source="internal_ledger",
        source_id=source_id,
        order_id=order_id,
        amount=amount,
        currency="INR",
        method="card",
        status="settled",
        fee=fee,
        tax_on_fee=tax_on_fee,
        settled_at=None,
        created_at=created_at,
        raw={"tax_on_fee": tax_on_fee, "refund_amount": refund_amount},
    )


def _bank_txn(order_id="order_1", amount=976.4, created_at="2025-06-01T12:00:00", source_id="BANK00001"):
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


def test_exact_match_within_tolerance():
    # ledger amount 1000, fee 20, tax_on_fee 3.6 -> expected net 976.4, matches bank exactly.
    ledger = [_ledger_txn()]
    bank = [_bank_txn(amount=976.4)]

    matches, rem_ledger, rem_bank = exact_match(ledger, bank)

    assert len(matches) == 1
    assert matches[0].ledger_row_id == "LEDG00001"
    assert matches[0].bank_row_id == "BANK00001"
    assert matches[0].tier == "exact"
    assert rem_ledger == []
    assert rem_bank == []


def test_exact_match_rejects_gap_beyond_tolerance():
    # Gap of 50 exceeds both the absolute (5) and percentage (1.5% of 1000 = 15) tolerance.
    ledger = [_ledger_txn()]
    bank = [_bank_txn(amount=976.4 - 50)]

    matches, rem_ledger, rem_bank = exact_match(ledger, bank)

    assert matches == []
    assert len(rem_ledger) == 1
    assert len(rem_bank) == 1


def test_exact_match_rejects_timestamp_beyond_tolerance():
    # Amount matches exactly, but bank timestamp is 10 hours after ledger — beyond the 6h tolerance.
    ledger = [_ledger_txn(created_at="2025-06-01T00:00:00")]
    bank = [_bank_txn(amount=976.4, created_at="2025-06-01T10:00:00")]

    matches, rem_ledger, rem_bank = exact_match(ledger, bank)

    assert matches == []
    assert len(rem_ledger) == 1
    assert len(rem_bank) == 1


def test_exact_match_skips_ambiguous_group_sizes():
    # Two ledger rows for the same order_id (duplicate injection) -> not "exact",
    # falls through to the fuzzy tier untouched.
    ledger = [
        _ledger_txn(source_id="LEDG00001"),
        _ledger_txn(source_id="LEDG00002"),
    ]
    bank = [_bank_txn(amount=976.4)]

    matches, rem_ledger, rem_bank = exact_match(ledger, bank)

    assert matches == []
    assert len(rem_ledger) == 2
    assert len(rem_bank) == 1


def test_exact_match_only_pairs_within_same_order_id():
    ledger = [_ledger_txn(order_id="order_1")]
    bank = [_bank_txn(order_id="order_2", amount=976.4)]

    matches, rem_ledger, rem_bank = exact_match(ledger, bank)

    assert matches == []
    assert len(rem_ledger) == 1
    assert len(rem_bank) == 1


def test_exact_match_accounts_for_refund_in_expected_net():
    # Refund of 200 must be subtracted from expected net alongside fee/tax.
    ledger = [_ledger_txn(amount=1000.0, fee=20.0, tax_on_fee=3.6, refund_amount=200.0)]
    bank = [_bank_txn(amount=776.4)]  # 1000 - 20 - 3.6 - 200

    matches, _, _ = exact_match(ledger, bank)

    assert len(matches) == 1
