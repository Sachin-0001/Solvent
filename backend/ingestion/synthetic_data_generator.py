"""
Generates the synthetic side of the three-source reconciliation problem.

Design: the "base transactions" set is the ground truth — 100% synthetic, so
every ground-truth label is genuinely known, not inferred. Real Razorpay
test-mode payments are deliberately kept OUT of this set: a real payment's
true reconciliation/tax/forecast labels aren't independently knowable the way
an injected synthetic label is, so blending even a few of them in would make
those particular ground-truth entries assumed-correct rather than known-correct.
Real test-mode data is used only as a separate calibration input (see
`run_ingestion.fetch_calibration_transactions`) to sanity-check that the
synthetic distributions look realistic — it never enters this truth set.

From the truth set we independently derive an internal-ledger export and a
bank-statement export, each with deliberately injected mismatches: rounding
differences, timestamp drift, and missing/duplicate rows. `build_ground_truth`
records exactly what was injected so the reconciliation engine (step 2) can be
scored honestly instead of self-reported.

Also carries the extra feature columns (payment_method, day_of_week, dispute/refund
flags, etc.) that the step-4 forecaster models will train on — generated once here
so every downstream stage works off one consistent synthetic dataset.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet"]
PAYMENT_METHOD_WEIGHTS = [0.35, 0.45, 0.12, 0.08]

MERCHANT_CATEGORIES = ["ecommerce", "food_delivery", "saas", "travel", "retail"]

# Fixed 2025 Indian public holidays covering a plausible synthetic date range.
HOLIDAYS = {
    "2025-01-26",  # Republic Day
    "2025-03-14",  # Holi
    "2025-04-18",  # Good Friday
    "2025-05-01",  # May Day
    "2025-08-15",  # Independence Day
    "2025-10-02",  # Gandhi Jayanti
    "2025-10-21",  # Diwali
    "2025-12-25",  # Christmas
}

BASE_FEE_PCT = {
    "card": 0.020,
    "upi": 0.000,
    "netbanking": 0.018,
    "wallet": 0.015,
}
BASE_DAYS_TO_SETTLE = {
    "card": 2,
    "upi": 1,
    "netbanking": 2,
    "wallet": 1,
}


def _random_datetime(start: datetime, end: datetime, rng: random.Random) -> datetime:
    delta_seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randint(0, delta_seconds))


def _is_weekend_or_holiday(dt: datetime) -> bool:
    return dt.weekday() >= 5 or dt.strftime("%Y-%m-%d") in HOLIDAYS


def generate_base_transactions(
    n_synthetic: int,
    start_date: str = "2025-06-01",
    end_date: str = "2025-08-31",
    seed: int = 42,
) -> list[dict[str, Any]]:
    """
    Builds the truth set: `n_synthetic` purely-synthetic base transactions,
    every one with a genuinely known ground-truth label. No real Razorpay data
    is blended in here — see the module docstring for why.
    """
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)

    base: list[dict[str, Any]] = []
    counter = 1

    for _ in range(n_synthetic):
        rng = random.Random((seed * 1_000_003 + counter) ^ 0x9E3779B9)
        created_at = _random_datetime(start, end, rng)
        amount = round(rng.uniform(150, 25000), 2)
        method = rng.choices(PAYMENT_METHODS, PAYMENT_METHOD_WEIGHTS)[0]
        base.append(
            _build_transaction_record(
                txn_id=f"TXN{counter:05d}",
                order_id=f"order_synth_{counter}",
                amount=amount,
                method=method,
                created_at=created_at,
                rng=rng,
            )
        )
        counter += 1

    base.sort(key=lambda t: t["created_at"])
    return base


def _build_transaction_record(
    *,
    txn_id: str,
    order_id: str,
    amount: float,
    method: str,
    created_at: datetime,
    rng: random.Random,
) -> dict[str, Any]:
    merchant_category = rng.choice(MERCHANT_CATEGORIES)
    had_dispute = rng.random() < 0.04
    had_refund = rng.random() < 0.08
    refund_amount = round(amount * rng.uniform(0.2, 1.0), 2) if had_refund else 0.0
    gst_on_fee_flag = rng.random() > 0.03  # GST on fees applies almost always

    fee_pct = max(0.0, BASE_FEE_PCT[method] + rng.gauss(0, 0.002))
    fee_amount = round(amount * fee_pct, 2)
    tax_on_fee = round(fee_amount * 0.18, 2) if gst_on_fee_flag else 0.0

    settle_days = BASE_DAYS_TO_SETTLE[method]
    if _is_weekend_or_holiday(created_at):
        settle_days += rng.choice([1, 2])
    if had_dispute:
        settle_days += rng.randint(3, 10)
    settle_days = max(0, settle_days + rng.choice([-1, 0, 0, 0, 1]))

    deduction_pct = round(
        ((fee_amount + tax_on_fee + refund_amount) / amount) if amount else 0.0, 4
    )

    settled_at = created_at + timedelta(days=settle_days, hours=rng.randint(0, 20))

    # ~2% of transactions: the gateway hasn't computed/swept the fee yet at
    # classification time (mirrors the real razorpay_adapter.py comment that
    # settlement fee/tax fields are often None on fresh test-mode payments).
    # This is a genuine data gap, not manufactured business-logic ambiguity —
    # it's what should make the tax matcher's rule engine actually decline to
    # classify and fall through to the LLM tier (see tax_matcher/rules.py).
    fee_amount_pending = rng.random() < 0.02

    # Deterministic from visible fields only (had_refund, gst_on_fee_flag, fee_amount)
    # so the rule-based tax matcher can actually be scored honestly against this —
    # a label with hidden randomness baked in would be unlearnable by design.
    if had_refund:
        true_tax_category = "refund_credit_note"
    elif not gst_on_fee_flag:
        true_tax_category = "exempt"
    elif fee_amount > 0:
        true_tax_category = "gst_on_fee"
    else:
        true_tax_category = "taxable_sale"

    status = "refunded" if had_refund else ("disputed" if had_dispute else "settled")

    return {
        "txn_id": txn_id,
        "source": "synthetic",
        "razorpay_payment_id": None,
        "order_id": order_id,
        "txn_amount": amount,
        "payment_method": method,
        "created_at": created_at.isoformat(),
        "day_of_week": created_at.weekday(),
        "is_weekend_or_holiday": _is_weekend_or_holiday(created_at),
        "merchant_category": merchant_category,
        "had_dispute_flag": had_dispute,
        "had_refund": had_refund,
        "refund_amount": refund_amount,
        "gst_on_fee_flag": gst_on_fee_flag,
        "fee_amount": fee_amount,
        "fee_amount_pending": fee_amount_pending,
        "tax_on_fee": tax_on_fee,
        "fee_pct": round(fee_pct, 4),
        "days_to_settle": settle_days,
        "deduction_pct": deduction_pct,
        "settled_at": settled_at.isoformat(),
        "status": status,
        "true_tax_category": true_tax_category,
    }


# --- Mismatch injection -----------------------------------------------------

MISMATCH_WEIGHTS = {
    "exact": 0.62,
    "rounding": 0.10,
    "timestamp_drift": 0.10,
    "missing": 0.05,
    "duplicate": 0.05,
    # --- Ambiguous kinds: deliberately land near/outside the fuzzy tier's
    # tolerance so they surface as exceptions a *human* has to adjudicate,
    # rather than cases with one obvious answer. Before these existed every
    # exception was "the counterpart genuinely doesn't exist", which needs no
    # judgment at all. See docs/metrics.md Stage 2 for the measured effect.
    "partial_settlement": 0.03,
    "late_settlement_window": 0.03,
    "refund_not_debited": 0.02,
}

# Amount tolerance in fuzzy_match is max(₹30, 8% of gross), and because amounts
# are uniform(150, 25_000) the percentage term dominates for all but 2 of 250
# rows. That makes the amount band a *cliff*, not a gradient — measured: a
# fixed 8.0% drift falls inside tolerance for 250/250 rows, while 8.5% falls
# outside for 248/250. So a single fixed percentage can only produce an
# all-or-nothing population. PARTIAL_SETTLEMENT_RANGE deliberately straddles
# the 8% boundary so some injections auto-match (proving the engine still
# works) and the rest become genuinely near-miss exceptions.
PARTIAL_SETTLEMENT_RANGE = (0.89, 0.94)

# fuzzy_match allows ≤96h of drift. 92-96h lands inside (auto-matched);
# beyond that is outside but still a plausible real delay — a long weekend
# plus a bank holiday — which is exactly the "amounts match to the paisa but
# it's 5 days late" call a human should make rather than an engine.
LATE_SETTLEMENT_HOURS = (92, 140)

# Kinds where no correct pairing exists at all, so an engine that declines to
# match is behaving correctly and must not be scored as having missed one.
NON_RECONCILABLE_KINDS = {"missing"}

# Kinds where a human could legitimately decide either way. Asserting these
# "must match" would penalize the engine for correctly escalating; asserting
# they're unmatchable would hide that a counterpart does exist. They're
# excluded from the recall denominator and reported separately instead.
AMBIGUOUS_KINDS = {"partial_settlement"}


def _inject_rows(
    base_transactions: list[dict[str, Any]],
    row_prefix: str,
    seed: int,
    amount_field: str,
    extra_fields_fn,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """
    Shared row-generation logic for both the ledger and bank-statement exports.
    Returns (rows, mismatch_map) where mismatch_map keys are txn_id.
    """
    rows: list[dict[str, Any]] = []
    mismatch_map: dict[str, dict[str, Any]] = {}
    row_counter = 1

    kinds = list(MISMATCH_WEIGHTS.keys())
    weights = list(MISMATCH_WEIGHTS.values())

    for txn in base_transactions:
        # Seeded from the stable numeric suffix of txn_id (not list position),
        # so a given transaction's injected mismatch is reproducible even if
        # base_transactions' sort order shifts between generator runs, and
        # unrelated code changes elsewhere don't reshuffle this one's draws.
        txn_seed = int(txn["txn_id"][3:])
        rng = random.Random((seed * 1_000_003 + txn_seed) ^ 0x85EBCA6B)
        kind = rng.choices(kinds, weights)[0]
        amount = txn[amount_field]
        created_at = datetime.fromisoformat(txn["created_at"])

        row_ids: list[str] = []

        if kind == "missing":
            mismatch_map[txn["txn_id"]] = {"kind": kind, "row_ids": []}
            continue

        n_rows = 2 if kind == "duplicate" else 1
        for copy_index in range(n_rows):
            row_id = f"{row_prefix}{row_counter:05d}"
            row_counter += 1
            row_amount = amount
            row_time = created_at

            if kind == "rounding":
                row_amount = round(amount + rng.choice([-1, 1]) * rng.uniform(0.01, 2.0), 2)
            if kind == "timestamp_drift":
                row_time = created_at + timedelta(minutes=rng.randint(-720, 720))

            # A duplicate used to emit two byte-identical rows, which made the
            # orphan trivially identifiable and never exercised the fuzzy
            # tier's scoring. Drifting only the *second* copy turns it into a
            # real question: two similar credits against one ledger entry —
            # double payout to claw back, or two genuine payments?
            if kind == "duplicate" and copy_index == 1:
                row_amount = round(amount * (1 + rng.uniform(0.02, 0.05)), 2)
                row_time = created_at + timedelta(minutes=rng.randint(30, 180))

            # Only part of the payout was released this cycle (rolling reserve
            # or a risk hold); the remainder settles later and isn't in this
            # statement window.
            if kind == "partial_settlement":
                row_amount = round(amount * rng.uniform(*PARTIAL_SETTLEMENT_RANGE), 2)

            # Amount is exact to the paisa; only the settlement date slipped.
            if kind == "late_settlement_window":
                row_time = created_at + timedelta(hours=rng.randint(*LATE_SETTLEMENT_HOURS))

            # The bank credited the payout without the refund deducted yet —
            # the refund debit lands in a later cycle. Measured: all 17 refund
            # transactions exceed fuzzy tolerance when the refund isn't
            # accounted for, so this reliably becomes an exception. On rows
            # with no refund there's nothing to withhold, so it degrades to a
            # clean row rather than a fake discrepancy.
            if kind == "refund_not_debited":
                row_amount = round(amount + (txn.get("refund_amount") or 0.0), 2)

            row = {
                "row_id": row_id,
                "txn_id_hint": txn["txn_id"],  # NOT visible to the reconciliation engine
                "order_id": txn["order_id"],
                "amount": row_amount,
                "timestamp": row_time.isoformat(),
                **extra_fields_fn(txn, rng),
            }
            rows.append(row)
            row_ids.append(row_id)

        mismatch_map[txn["txn_id"]] = {"kind": kind, "row_ids": row_ids}

    return rows, mismatch_map


def generate_internal_ledger(
    base_transactions: list[dict[str, Any]], seed: int = 101
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    def extra(txn: dict[str, Any], rng: random.Random) -> dict[str, Any]:
        # The merchant's own ledger legitimately knows its fee, GST-on-fee, and
        # refund figures — it's their system that recorded the refund. The bank
        # statement, generated separately below, only ever sees a net credit.
        return {
            "payment_method": txn["payment_method"],
            "status": txn["status"],
            "fee_amount": txn["fee_amount"],
            "tax_on_fee": txn["tax_on_fee"],
            "refund_amount": txn["refund_amount"],
        }

    return _inject_rows(base_transactions, "LEDG", seed, "txn_amount", extra)


def generate_bank_statement(
    base_transactions: list[dict[str, Any]], seed: int = 202
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    def extra(txn: dict[str, Any], rng: random.Random) -> dict[str, Any]:
        # Bank sees the net settled amount, not the gross transaction amount.
        net = round(
            txn["txn_amount"] - txn["fee_amount"] - txn["tax_on_fee"] - txn["refund_amount"], 2
        )
        return {
            "utr_reference": f"UTR{rng.randint(10**9, 10**10 - 1)}" if rng.random() > 0.1 else None,
            "type": "credit",
        }

    # Bank statement amounts are net-of-deduction, so override amount_field logic
    # by pre-computing a "bank_amount" pseudo-field on each txn before calling.
    enriched = []
    for txn in base_transactions:
        t = dict(txn)
        t["bank_amount"] = round(
            txn["txn_amount"] - txn["fee_amount"] - txn["tax_on_fee"] - txn["refund_amount"], 2
        )
        enriched.append(t)

    return _inject_rows(enriched, "BANK", seed, "bank_amount", extra)


def _verdict(ledger_kind: str, bank_kind: str) -> str:
    """
    What an ideal engine *should* do with this transaction — declared per
    mismatch kind rather than inferred from "is it missing?", so the recall
    denominator means something specific:

      no_counterpart — a side is genuinely absent; declining to match is correct
      ambiguous      — a counterpart exists but a human could decide either way;
                       excluded from recall so the engine is neither rewarded
                       for force-matching nor punished for escalating
      must_match     — the counterpart exists and genuinely corresponds; failing
                       to pair it is a real miss and should cost recall
    """
    kinds = {ledger_kind, bank_kind}
    if kinds & NON_RECONCILABLE_KINDS:
        return "no_counterpart"
    if kinds & AMBIGUOUS_KINDS:
        return "ambiguous"
    return "must_match"


def build_ground_truth(
    base_transactions: list[dict[str, Any]],
    ledger_mismatch_map: dict[str, dict[str, Any]],
    bank_mismatch_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    ground_truth = []
    for txn in base_transactions:
        txn_id = txn["txn_id"]
        ledger_info = ledger_mismatch_map.get(txn_id, {"kind": "missing", "row_ids": []})
        bank_info = bank_mismatch_map.get(txn_id, {"kind": "missing", "row_ids": []})
        ground_truth.append(
            {
                "txn_id": txn_id,
                "order_id": txn["order_id"],
                "ledger_row_ids": ledger_info["row_ids"],
                "bank_row_ids": bank_info["row_ids"],
                "ledger_mismatch": ledger_info["kind"],
                "bank_mismatch": bank_info["kind"],
                "should_fully_reconcile": _verdict(ledger_info["kind"], bank_info["kind"])
                == "must_match",
                "reconcile_verdict": _verdict(ledger_info["kind"], bank_info["kind"]),
            }
        )
    return ground_truth
