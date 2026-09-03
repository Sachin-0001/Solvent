"""
Cash-position engine: pure arithmetic over the two baseline forecasts, no
network/DB dependency — same style as the existing reconciliation tests.
"""

from __future__ import annotations

from backend.finance.cash_position import compute_cash_position


def _txn(created_at, settled_at=None, status="settled", txn_amount=1000.0,
         refund_amount=0.0, fee_amount=20.0, tax_on_fee=3.6):
    return {
        "created_at": created_at,
        "settled_at": settled_at or created_at,
        "status": status,
        "txn_amount": txn_amount,
        "refund_amount": refund_amount,
        "fee_amount": fee_amount,
        "tax_on_fee": tax_on_fee,
    }


def test_normal_positive_cash_flow():
    txns = [_txn("2025-06-01T10:00:00", settled_at="2025-06-02T10:00:00")]
    result = compute_cash_position(txns, current_cash=100_000.0)

    # net_settlement = 1000 - 0 - 20 - 3.6 = 976.4, no refunds observed that day.
    assert result["expected_settlement"] == 976.4
    assert result["expected_refunds"] == 0.0
    assert result["expected_net_cash_flow"] == 976.4
    assert result["projected_cash"] == 100_976.4
    assert result["current_cash"] == 100_000.0


def test_refunds_greater_than_settlement():
    settle_day = "2025-06-02T10:00:00"
    txns = [
        _txn("2025-06-01T10:00:00", settled_at=settle_day, txn_amount=500.0, fee_amount=10.0, tax_on_fee=1.8),
        _txn("2025-06-01T09:00:00", settled_at=None, status="pending", refund_amount=2000.0),
    ]
    result = compute_cash_position(txns, current_cash=10_000.0)

    # Refund total is read from created_at="today" (2025-06-01), independent
    # of settlement date, so it applies even though the refunded txn itself
    # never settled.
    assert result["expected_refunds"] == 2000.0
    assert result["expected_net_cash_flow"] == round(result["expected_settlement"] - 2000.0, 2)
    assert result["projected_cash"] == round(10_000.0 + result["expected_net_cash_flow"], 2)
    assert result["expected_net_cash_flow"] < 0


def test_zero_refunds():
    txns = [_txn("2025-06-01T10:00:00", settled_at="2025-06-02T10:00:00")]
    result = compute_cash_position(txns, current_cash=0.0)
    assert result["expected_refunds"] == 0.0
    assert result["projected_cash"] == result["expected_settlement"]


def test_zero_settlement_history():
    txns = [_txn("2025-06-01T10:00:00", settled_at=None, status="pending")]
    result = compute_cash_position(txns, current_cash=5_000.0)
    assert result["expected_settlement"] == 0.0
    assert result["projected_cash"] == 5_000.0 - result["expected_refunds"]


def test_deterministic_projected_cash_formula():
    txns = [_txn("2025-06-01T10:00:00", settled_at="2025-06-02T10:00:00")]
    result = compute_cash_position(txns, current_cash=50_000.0)
    expected = round(
        result["current_cash"] + result["expected_settlement"] - result["expected_refunds"], 2
    )
    assert result["projected_cash"] == expected
    assert result["expected_net_cash_flow"] == round(
        result["expected_settlement"] - result["expected_refunds"], 2
    )


def test_forecast_method_is_naive_not_ml():
    txns = [_txn("2025-06-01T10:00:00", settled_at="2025-06-02T10:00:00")]
    result = compute_cash_position(txns, current_cash=0.0)
    assert result["forecast_method"]["settlement"]["method"] == "naive_previous_day"
    assert result["forecast_method"]["settlement"]["model"] is None
    assert result["forecast_method"]["refunds"]["method"] == "naive_previous_day"
    assert result["forecast_method"]["refunds"]["model"] is None
