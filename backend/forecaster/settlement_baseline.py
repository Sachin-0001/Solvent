"""
Production settlement forecast — a deterministic naive baseline, NOT a
trained model. ML/notebooks/model_a_days_to_settle_training.ipynb's
"Settlement Model" section tested a LinearRegression on the same lag/rolling
daily-aggregate recipe used for GMV and found it 54.87% worse than simply
predicting tomorrow's net settlement as today's total (Linear Regression MAE
~144,930.50 vs. naive MAE ~93,583.45) — so that model is deliberately not
deployed here.

expected_settlement_tomorrow = total_settlement_today
  where total_settlement_today = sum(txn_amount - refund_amount - fee_amount
  - tax_on_fee) over transactions with status == "settled" whose
  settlement_date == today.

This baseline exists behind `forecast_next_day_settlement` specifically so it
can be swapped for a genuine per-transaction settlement pipeline later
(created_at + days_to_settle + amount/fees/refunds/tax/status -> expected
transactions settling tomorrow, using Model A/B's per-transaction predictions
— see backend/forecaster/predict.py) without changing any caller: the cash
engine (backend/finance/cash_position.py) only depends on this function's
return shape, not on how the number inside it was produced.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def _parse_naive(dt_str: str) -> datetime:
    dt = datetime.fromisoformat(dt_str)
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def _net_settlement(txn: dict[str, Any]) -> float:
    return (
        (txn.get("txn_amount") or 0.0)
        - (txn.get("refund_amount") or 0.0)
        - (txn.get("fee_amount") or 0.0)
        - (txn.get("tax_on_fee") or 0.0)
    )


def forecast_next_day_settlement(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Returns tomorrow's expected net settlement as today's net-settled
    total (today = the most recent settlement date among status=="settled"
    rows). Returns 0.0 with an explicit note when there isn't enough settled
    history, rather than raising — an empty/early dataset is a legitimate
    state, not an error."""
    settled = [t for t in transactions if t.get("status") == "settled" and t.get("settled_at")]
    if not settled:
        return {
            "value": 0.0,
            "method": "naive_previous_day",
            "model": None,
            "forecast_date": None,
            "based_on_date": None,
            "note": "No settled transaction history available.",
        }

    dated = [(_parse_naive(t["settled_at"]).date(), _net_settlement(t)) for t in settled]
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


__all__ = ["forecast_next_day_settlement"]
