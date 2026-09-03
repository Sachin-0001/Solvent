"""
Refund/settlement naive baselines — deterministic, no network/DB dependency.
These are the production-deployed forecasts (the notebook's LinearRegression
alternatives validated worse than naive-previous-day for both, see
docs/metrics.md), so pinning "returns previous day's total" and "handles
missing history safely" matters more here than for an ML model.
"""

from __future__ import annotations

from backend.forecaster.refund_baseline import forecast_next_day_refunds
from backend.forecaster.settlement_baseline import forecast_next_day_settlement


def test_refund_forecast_returns_previous_day_total():
    txns = [
        {"created_at": "2025-06-01T10:00:00", "refund_amount": 100.0},
        {"created_at": "2025-06-01T14:00:00", "refund_amount": 50.0},
        {"created_at": "2025-05-31T10:00:00", "refund_amount": 999.0},
    ]
    result = forecast_next_day_refunds(txns)
    assert result["value"] == 150.0
    assert result["method"] == "naive_previous_day"
    assert result["model"] is None
    assert result["based_on_date"] == "2025-06-01"
    assert result["forecast_date"] == "2025-06-02"


def test_refund_forecast_handles_no_history():
    result = forecast_next_day_refunds([])
    assert result["value"] == 0.0
    assert result["forecast_date"] is None
    assert "note" in result


def test_refund_forecast_handles_missing_refund_field():
    txns = [{"created_at": "2025-06-01T10:00:00"}]  # no refund_amount key at all
    result = forecast_next_day_refunds(txns)
    assert result["value"] == 0.0


def test_settlement_forecast_returns_previous_day_total():
    txns = [
        {
            "settled_at": "2025-06-02T10:00:00", "status": "settled",
            "txn_amount": 1000.0, "refund_amount": 0.0, "fee_amount": 20.0, "tax_on_fee": 3.6,
        },
        {
            "settled_at": "2025-06-01T10:00:00", "status": "settled",
            "txn_amount": 500.0, "refund_amount": 0.0, "fee_amount": 10.0, "tax_on_fee": 1.8,
        },
    ]
    result = forecast_next_day_settlement(txns)
    assert result["value"] == 976.4
    assert result["method"] == "naive_previous_day"
    assert result["model"] is None
    assert result["based_on_date"] == "2025-06-02"
    assert result["forecast_date"] == "2025-06-03"


def test_settlement_forecast_ignores_unsettled_rows():
    txns = [
        {"settled_at": "2025-06-02T10:00:00", "status": "pending", "txn_amount": 1000.0,
         "refund_amount": 0.0, "fee_amount": 20.0, "tax_on_fee": 3.6},
    ]
    result = forecast_next_day_settlement(txns)
    assert result["value"] == 0.0
    assert "note" in result


def test_settlement_forecast_handles_no_history():
    result = forecast_next_day_settlement([])
    assert result["value"] == 0.0
    assert result["forecast_date"] is None
    assert "note" in result
