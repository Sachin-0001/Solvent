"""
Unified cash-position engine — Track 4's headline feature. Deterministic
arithmetic only: no LLM, no invented numbers.

    projected_cash = current_cash + expected_settlement - expected_refunds

`current_cash` is never fabricated: the synthetic dataset has no authoritative
opening-balance field, so it must be supplied by the caller (the API exposes
it as a required-with-default query param — see backend/api.py). Everything
else is computed from the application's own transaction data via the
existing, already-validated forecast functions:
  - expected_settlement: backend.forecaster.settlement_baseline (naive
    previous-day net-settlement baseline — the notebook's LinearRegression
    alternative validated worse than this baseline, so it isn't used)
  - expected_refunds: backend.forecaster.refund_baseline (naive previous-day
    baseline — same reasoning)

`net_settlement` (txn_amount - refund_amount - fee_amount - tax_on_fee,
computed inside settlement_baseline) already deducts refunds/fees/tax once;
`expected_refunds` here is a separate, forward-looking "how much do we expect
to pay out tomorrow" figure for cash-flow visibility, not a second deduction
applied to the same settlement total — so `expected_net_cash_flow` is
`expected_settlement - expected_refunds`, not double-subtracting refunds that
are already netted out of expected_settlement's *historical* observation.
"""

from __future__ import annotations

from typing import Any

from backend.forecaster.refund_baseline import forecast_next_day_refunds
from backend.forecaster.settlement_baseline import forecast_next_day_settlement


def compute_cash_position(transactions: list[dict[str, Any]], current_cash: float) -> dict[str, Any]:
    settlement = forecast_next_day_settlement(transactions)
    refunds = forecast_next_day_refunds(transactions)

    expected_settlement = settlement["value"]
    expected_refunds = refunds["value"]
    expected_net_cash_flow = round(expected_settlement - expected_refunds, 2)
    projected_cash = round(current_cash + expected_net_cash_flow, 2)

    forecast_date = settlement["forecast_date"] or refunds["forecast_date"]

    return {
        "current_cash": round(float(current_cash), 2),
        "expected_settlement": expected_settlement,
        "expected_refunds": expected_refunds,
        "expected_net_cash_flow": expected_net_cash_flow,
        "projected_cash": projected_cash,
        "forecast_date": forecast_date,
        "forecast_method": {
            "settlement": {
                "method": settlement["method"],
                "model": settlement["model"],
                "based_on_date": settlement["based_on_date"],
            },
            "refunds": {
                "method": refunds["method"],
                "model": refunds["model"],
                "based_on_date": refunds["based_on_date"],
            },
        },
    }


__all__ = ["compute_cash_position"]
