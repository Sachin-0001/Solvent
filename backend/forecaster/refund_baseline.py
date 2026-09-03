"""
Production refund forecast — a deterministic naive baseline, NOT a trained
model. ML/notebooks/model_a_days_to_settle_training.ipynb's "Refund Model"
section tested a LinearRegression on the same lag/rolling daily-aggregate
recipe used for GMV and found it 46.15% worse than simply predicting
tomorrow's refunds as today's total (Linear Regression MAE ~12,536.87 vs.
naive MAE ~8,578.12) — so that model is deliberately not deployed here.

expected_refunds_tomorrow = total_refunds_today
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def _parse_naive(dt_str: str) -> datetime:
    dt = datetime.fromisoformat(dt_str)
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def forecast_next_day_refunds(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Returns tomorrow's expected total refunds as today's total refund
    amount (today = the most recent date present in `transactions`). Returns
    a value of 0.0 with an explicit note when there's no refund history at
    all, rather than raising — "no refunds yet" is a legitimate state, not
    an error."""
    if not transactions:
        return {
            "value": 0.0,
            "method": "naive_previous_day",
            "model": None,
            "forecast_date": None,
            "based_on_date": None,
            "note": "No transaction history available.",
        }

    dated = [(_parse_naive(t["created_at"]).date(), t.get("refund_amount") or 0.0) for t in transactions]
    latest_date = max(d for d, _ in dated)
    today_total = sum(amount for d, amount in dated if d == latest_date)
    forecast_date = (latest_date + timedelta(days=1)).isoformat()

    return {
        "value": round(float(today_total), 2),
        "method": "naive_previous_day",
        "model": None,
        "forecast_date": forecast_date,
        "based_on_date": latest_date.isoformat(),
    }


__all__ = ["forecast_next_day_refunds"]
