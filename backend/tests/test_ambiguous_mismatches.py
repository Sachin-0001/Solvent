"""
The ambiguous mismatch kinds and the ground-truth verdict classification.

These exist because every exception used to be "the counterpart genuinely
doesn't exist" — a case with one obvious answer, which gives a human reviewer
nothing to actually decide. The tests below pin the two properties that make
the new kinds meaningful: they land where the engine *can't* auto-resolve
them, and ground truth labels them honestly so recall isn't quietly gamed.
"""

from __future__ import annotations

from backend.ingestion.synthetic_data_generator import (
    AMBIGUOUS_KINDS,
    LATE_SETTLEMENT_HOURS,
    MISMATCH_WEIGHTS,
    NON_RECONCILABLE_KINDS,
    PARTIAL_SETTLEMENT_RANGE,
    _verdict,
    build_ground_truth,
    generate_base_transactions,
    generate_bank_statement,
    generate_internal_ledger,
)

# Mirrors fuzzy_match.py's constants. Duplicated deliberately: if either side
# drifts, these tests should fail loudly rather than silently track the change.
FUZZY_AMOUNT_TOL_ABS = 30.0
FUZZY_AMOUNT_TOL_PCT = 0.08
FUZZY_TIMESTAMP_TOL_HOURS = 96


def test_mismatch_weights_still_sum_to_one():
    # rng.choices normalizes internally, so a drift here wouldn't raise — it
    # would just silently change every documented distribution instead.
    assert abs(sum(MISMATCH_WEIGHTS.values()) - 1.0) < 1e-9


def test_partial_settlement_range_straddles_the_fuzzy_amount_cliff():
    """The amount band is a cliff, not a gradient: measured, a flat 8.0% drift
    is inside tolerance for every row while 8.5% is outside for 248/250. A
    single fixed percentage therefore yields an all-or-nothing population,
    which is the very problem these kinds exist to avoid — so the range must
    span the boundary."""
    lo_gap = 1 - PARTIAL_SETTLEMENT_RANGE[1]  # smallest shortfall
    hi_gap = 1 - PARTIAL_SETTLEMENT_RANGE[0]  # largest shortfall
    assert lo_gap < FUZZY_AMOUNT_TOL_PCT < hi_gap


def test_late_settlement_window_straddles_the_96h_boundary():
    assert LATE_SETTLEMENT_HOURS[0] <= FUZZY_TIMESTAMP_TOL_HOURS < LATE_SETTLEMENT_HOURS[1]


def test_verdict_classifies_the_three_cases_distinctly():
    assert _verdict("missing", "exact") == "no_counterpart"
    assert _verdict("exact", "missing") == "no_counterpart"
    assert _verdict("partial_settlement", "exact") == "ambiguous"
    assert _verdict("exact", "exact") == "must_match"
    assert _verdict("late_settlement_window", "exact") == "must_match"


def test_no_counterpart_outranks_ambiguous():
    """If a side is genuinely absent there is nothing to adjudicate, so the
    absence must win — otherwise an unmatchable row would be presented to a
    reviewer as a judgment call."""
    assert _verdict("missing", "partial_settlement") == "no_counterpart"


def test_ambiguous_kinds_are_excluded_from_the_recall_denominator():
    """An ambiguous case must not be asserted as "must match": that would
    penalize the engine for correctly escalating a call only a human can
    make. Equally it must not be lumped in with no_counterpart, which would
    hide that a counterpart does exist."""
    for kind in AMBIGUOUS_KINDS:
        assert _verdict(kind, "exact") == "ambiguous"
        assert kind not in NON_RECONCILABLE_KINDS


def test_ground_truth_carries_a_verdict_for_every_transaction():
    base = generate_base_transactions(n_synthetic=120, seed=42)
    _, ledger_map = generate_internal_ledger(base)
    _, bank_map = generate_bank_statement(base)
    gt = build_ground_truth(base, ledger_map, bank_map)

    assert len(gt) == len(base)
    for g in gt:
        assert g["reconcile_verdict"] in {"must_match", "ambiguous", "no_counterpart"}
        # The boolean must stay consistent with the verdict it's derived from,
        # since validate.py's recall reads the boolean.
        assert g["should_fully_reconcile"] == (g["reconcile_verdict"] == "must_match")


def test_generator_produces_all_three_verdicts_at_realistic_volume():
    """A dataset with no ambiguous rows would make the review queue a
    demo of nothing, so assert the injection actually fires."""
    base = generate_base_transactions(n_synthetic=250, seed=42)
    _, ledger_map = generate_internal_ledger(base)
    _, bank_map = generate_bank_statement(base)
    gt = build_ground_truth(base, ledger_map, bank_map)

    verdicts = {g["reconcile_verdict"] for g in gt}
    assert verdicts == {"must_match", "ambiguous", "no_counterpart"}


def test_refund_not_debited_exceeds_tolerance_on_refunded_rows():
    """The scenario only bites when a refund exists to withhold — measured,
    all 17 refund transactions exceed fuzzy tolerance when the refund isn't
    deducted, while fee+tax alone never does (0/250)."""
    base = generate_base_transactions(n_synthetic=250, seed=42)
    refunded = [t for t in base if t["had_refund"]]
    assert refunded, "expected some refunded transactions in the fixture"

    for txn in refunded:
        tol = max(FUZZY_AMOUNT_TOL_ABS, FUZZY_AMOUNT_TOL_PCT * txn["txn_amount"])
        assert txn["refund_amount"] > tol


def test_generation_is_deterministic_for_a_fixed_seed():
    first = build_ground_truth(
        base := generate_base_transactions(n_synthetic=80, seed=42),
        generate_internal_ledger(base)[1],
        generate_bank_statement(base)[1],
    )
    base2 = generate_base_transactions(n_synthetic=80, seed=42)
    second = build_ground_truth(
        base2, generate_internal_ledger(base2)[1], generate_bank_statement(base2)[1]
    )
    assert first == second
