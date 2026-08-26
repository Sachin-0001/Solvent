"""
Generates the synthetic side of the three-source reconciliation problem.

Design: a set of "base transactions" is the ground truth (real Razorpay payments
when available, padded with synthetic ones to reach a usable volume — test-mode
accounts rarely have enough real traffic on their own). From that truth set we
independently derive an internal-ledger export and a bank-statement export, each
with deliberately injected mismatches: rounding differences, timestamp drift, and
missing/duplicate rows. `build_ground_truth` records exactly what was injected so
the reconciliation engine (step 2) can be scored honestly instead of self-reported.

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
    real_transactions: list[dict[str, Any]] | None = None,
    start_date: str = "2025-06-01",
    end_date: str = "2025-08-31",
    seed: int = 42,
) -> list[dict[str, Any]]:
    """
    Builds the truth set. Real Razorpay payments (already-normalized dicts with
    at minimum amount/method/created_at) are included as-is, tagged
    source="razorpay_real". `n_synthetic` additional purely-synthetic base
    transactions are generated on top to reach a workable dataset size.
    """
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)

    base: list[dict[str, Any]] = []
    counter = 1

    for real in real_transactions or []:
        # Each transaction gets its own RNG derived from (seed, counter) rather
        # than sharing one stream across the whole loop — a code change that
        # adds/removes a random draw for one transaction (or one field) no
        # longer shifts every transaction generated after it. Bit-mixing the
        # seed avoids the trivial correlation plain addition would leave
        # between adjacent per-txn streams.
        rng = random.Random((seed * 1_000_003 + counter) ^ 0x9E3779B9)
        created_at = datetime.fromisoformat(real["created_at"])
        method = real.get("method") or rng.choices(PAYMENT_METHODS, PAYMENT_METHOD_WEIGHTS)[0]
        base.append(
            _build_transaction_record(
                txn_id=f"TXN{counter:05d}",
                source="razorpay_real",
                order_id=real.get("order_id") or f"order_real_{counter}",
                amount=real["amount"],
                method=method,
                created_at=created_at,
                rng=rng,
                razorpay_payment_id=real.get("source_id"),
            )
        )
        counter += 1

    for _ in range(n_synthetic):
        rng = random.Random((seed * 1_000_003 + counter) ^ 0x9E3779B9)
        created_at = _random_datetime(start, end, rng)
        amount = round(rng.uniform(150, 25000), 2)
        method = rng.choices(PAYMENT_METHODS, PAYMENT_METHOD_WEIGHTS)[0]
        base.append(
            _build_transaction_record(
                txn_id=f"TXN{counter:05d}",
                source="synthetic",
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
    source: str,
    order_id: str,
    amount: float,
    method: str,
    created_at: datetime,
    rng: random.Random,
    razorpay_payment_id: str | None = None,
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
        "source": source,
        "razorpay_payment_id": razorpay_payment_id,
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
    "exact": 0.70,
    "rounding": 0.10,
    "timestamp_drift": 0.10,
    "missing": 0.05,
    "duplicate": 0.05,
}


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
        for _ in range(n_rows):
            row_id = f"{row_prefix}{row_counter:05d}"
            row_counter += 1
            row_amount = amount
            row_time = created_at

            if kind == "rounding":
                row_amount = round(amount + rng.choice([-1, 1]) * rng.uniform(0.01, 2.0), 2)
            if kind == "timestamp_drift":
                row_time = created_at + timedelta(minutes=rng.randint(-720, 720))

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
                "should_fully_reconcile": (
                    ledger_info["kind"] != "missing" and bank_info["kind"] != "missing"
                ),
            }
        )
    return ground_truth
