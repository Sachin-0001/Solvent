"""
Shared prediction utilities built on the two trained models. Used by the Q&A
agent (forward-looking questions) and, in step 6, the frontend's 7-day cash
forecast endpoint — one source of truth for "what will settle, and when."
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import joblib

from backend.forecaster.features import (
    MODEL_A_CATEGORICAL,
    MODEL_A_NUMERIC,
    MODEL_B_CATEGORICAL,
    MODEL_B_NUMERIC,
    to_frame,
)
from backend.config import MODELS_DIR


def _parse_naive(dt_str: str) -> datetime:
    """Real Razorpay timestamps carry a UTC offset; synthetic ones don't. Drop
    tzinfo so the two sources can be compared/subtracted without crashing."""
    dt = datetime.fromisoformat(dt_str)
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


_model_a = None
_model_b = None
_metrics_cache: dict[str, Any] | None = None


def _load_models():
    global _model_a, _model_b
    if _model_a is None:
        _model_a = joblib.load(MODELS_DIR / "model_a_days_to_settle.joblib")
    if _model_b is None:
        _model_b = joblib.load(MODELS_DIR / "model_b_deduction_pct.joblib")
    return _model_a, _model_b


def _load_mae() -> tuple[float, float]:
    """Returns (model_a_mae_days, model_b_mae_deduction_pct) from the last
    training report, used as a cheap, honest uncertainty band since plain
    LinearRegression has no native prediction interval."""
    global _metrics_cache
    if _metrics_cache is None:
        from backend import db

        _metrics_cache = {
            "model_a": db.load_forecaster_metrics("model_a"),
            "model_b": db.load_forecaster_metrics("model_b"),
        }
    return (
        _metrics_cache["model_a"]["chosen_mae"],
        _metrics_cache["model_b"]["chosen_mae"],
    )


def predict_transaction(txn: dict[str, Any]) -> dict[str, float]:
    """Predicts days_to_settle and deduction_pct for one transaction dict
    (must carry the raw feature fields — see features.py)."""
    model_a, model_b = _load_models()
    df = to_frame([txn])

    days_to_settle = float(model_a.predict(df[MODEL_A_NUMERIC + MODEL_A_CATEGORICAL])[0])
    deduction_pct = float(model_b.predict(df[MODEL_B_NUMERIC + MODEL_B_CATEGORICAL])[0])
    deduction_pct = max(0.0, min(1.0, deduction_pct))  # deduction can't be negative or >100%

    return {"predicted_days_to_settle": round(days_to_settle, 2), "predicted_deduction_pct": round(deduction_pct, 4)}


def forecast_daily_cashflow(
    transactions: list[dict[str, Any]],
    reference_date: str | None = None,
    horizon_days: int = 7,
) -> list[dict[str, Any]]:
    """
    Projects expected net settlement inflow for the `horizon_days` days
    following `reference_date` (defaults to the day after the latest
    transaction in the dataset, since the synthetic data lives in a fixed
    historical window rather than tracking real "today").

    For each transaction, predicted settlement date = created_at +
    predicted_days_to_settle, predicted net amount = txn_amount *
    (1 - predicted_deduction_pct). Transactions landing in the window are
    bucketed by day. The confidence band applies each model's held-out MAE as
    a simple, honest +/- range — not a Monte Carlo simulation.
    """
    # Only the deduction-% MAE is used for the band below (amount uncertainty);
    # model_a's day-level MAE isn't applied to shift transactions between day
    # buckets, to keep the band a simple, explainable amount range rather than
    # a full re-bucketing simulation.
    _mae_days, mae_deduction = _load_mae()

    if reference_date is None:
        latest = max(_parse_naive(t["created_at"]) for t in transactions)
        reference_date = (latest + timedelta(days=1)).date().isoformat()
    ref = _parse_naive(reference_date)
    horizon_end = ref + timedelta(days=horizon_days)

    buckets: dict[str, dict[str, float]] = {
        (ref + timedelta(days=i)).date().isoformat(): {"expected": 0.0, "lower": 0.0, "upper": 0.0}
        for i in range(horizon_days)
    }

    for txn in transactions:
        prediction = predict_transaction(txn)
        created_at = _parse_naive(txn["created_at"])
        settle_date = created_at + timedelta(days=prediction["predicted_days_to_settle"])
        if not (ref <= settle_date < horizon_end):
            continue

        day_key = settle_date.date().isoformat()
        deduction = prediction["predicted_deduction_pct"]
        net = txn["txn_amount"] * (1 - deduction)
        net_low = txn["txn_amount"] * (1 - min(1.0, deduction + mae_deduction))
        net_high = txn["txn_amount"] * (1 - max(0.0, deduction - mae_deduction))

        buckets[day_key]["expected"] += net
        buckets[day_key]["lower"] += net_low
        buckets[day_key]["upper"] += net_high

    return [
        {
            "date": day,
            "expected_amount": round(v["expected"], 2),
            "lower_bound": round(v["lower"], 2),
            "upper_bound": round(v["upper"], 2),
        }
        for day, v in sorted(buckets.items())
    ]
