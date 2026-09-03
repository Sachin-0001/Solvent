"""
Q&A agent tools: pure Python over in-memory record lists, no network/DB
dependency — same style as the reconciliation/cash-position tests. These are
the functions Groq's tool-calling loop actually invokes (backend/qa_agent/agent.py);
pinning their filtering/aggregation behavior matters since the LLM only
narrates whatever they return.
"""

from __future__ import annotations

from backend.qa_agent.tools import (
    find_relation,
    generate_audit_report,
    search_invoices,
    search_payments,
    search_settlements,
)


def _record(**overrides):
    base = {
        "txn_id": "TXN001",
        "order_id": "order_1",
        "txn_amount": 1000.0,
        "payment_method": "card",
        "created_at": "2025-06-01T10:00:00",
        "settled_at": "2025-06-02T10:00:00",
        "status": "settled",
        "had_refund": False,
        "refund_amount": 0.0,
        "had_dispute_flag": False,
        "reconciliation_status": "matched",
        "reconciliation_tier": "exact",
        "tax_category": "gst_on_fee",
        "tax_reasoning": "Nonzero fee with GST applicable.",
        "days_to_settle": 1,
        "fee_amount": 20.0,
        "tax_on_fee": 3.6,
    }
    base.update(overrides)
    return base


def test_search_payments_filters_by_method_and_dispute():
    records = [
        _record(txn_id="TXN001", payment_method="card", had_dispute_flag=False),
        _record(txn_id="TXN002", payment_method="wallet", had_dispute_flag=True),
    ]
    result = search_payments(records, payment_method="wallet", had_dispute_flag=True)
    assert result["total_matched"] == 1
    assert result["records"][0]["txn_id"] == "TXN002"


def test_search_payments_by_order_id():
    records = [_record(order_id="order_1"), _record(txn_id="TXN002", order_id="order_2")]
    result = search_payments(records, order_id="order_2")
    assert result["total_matched"] == 1
    assert result["records"][0]["order_id"] == "order_2"


def test_search_settlements_only_returns_settled():
    records = [
        _record(txn_id="TXN001", status="settled", settled_at="2025-06-02T10:00:00"),
        _record(txn_id="TXN002", status="pending", settled_at=None),
    ]
    result = search_settlements(records)
    assert result["total_matched"] == 1
    assert result["records"][0]["txn_id"] == "TXN001"


def test_search_settlements_date_range_and_total():
    records = [
        _record(txn_id="TXN001", settled_at="2025-06-01T10:00:00", txn_amount=500.0),
        _record(txn_id="TXN002", settled_at="2025-06-05T10:00:00", txn_amount=700.0),
    ]
    result = search_settlements(records, settled_after="2025-06-03")
    assert result["total_matched"] == 1
    assert result["total_settlement_amount"] == 700.0


def test_search_invoices_maps_to_tax_classifications_honestly():
    records = [_record(txn_id="TXN001", tax_category="exempt")]
    result = search_invoices(records, category="exempt")
    assert result["total_matched"] == 1
    assert "no separate invoice store" in result["note"]


def test_search_invoices_excludes_unclassified_records():
    records = [_record(txn_id="TXN001", tax_category=None)]
    result = search_invoices(records)
    assert result["total_matched"] == 0


def test_find_relation_joins_transaction_reconciliation_and_tax():
    records = [
        _record(
            order_id="order_5", txn_id="TXN005", reconciliation_status="matched",
            reconciliation_tier="fuzzy", tax_category="taxable_sale",
        )
    ]
    result = find_relation(records, order_id="order_5")
    assert result["found"] is True
    assert result["transaction"]["txn_id"] == "TXN005"
    assert result["reconciliation"]["tier"] == "fuzzy"
    assert result["tax_classification"]["category"] == "taxable_sale"


def test_find_relation_reports_not_found_honestly():
    result = find_relation([_record(order_id="order_1")], order_id="order_missing")
    assert result["found"] is False


def test_find_relation_requires_an_identifier():
    result = find_relation([_record()])
    assert "error" in result


def test_generate_audit_report_aggregates_without_recomputing_pipeline_logic():
    records = [
        _record(txn_id="TXN001", reconciliation_status="matched", had_refund=False),
        _record(txn_id="TXN002", reconciliation_status="exception", had_refund=True, refund_amount=200.0),
    ]
    report = generate_audit_report(records)
    assert report["total_transactions"] == 2
    assert report["reconciliation"]["reconciled"] == 1
    assert report["reconciliation"]["exceptions"] == 1
    assert report["reconciliation"]["match_rate_pct"] == 50.0
    assert report["refunded_count"] == 1
    assert report["total_refund_amount"] == 200.0


def test_generate_audit_report_passes_through_cash_position_when_given():
    cp = {"projected_cash": 123.45}
    report = generate_audit_report([_record()], cash_position=cp)
    assert report["cash_position"] == cp
