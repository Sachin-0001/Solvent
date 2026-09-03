"""
Tax matcher rule engine: deterministic decision tree, zero LLM calls — the
other most testable piece of the pipeline. Includes the fee_amount_pending
data-gap case (see docs/metrics.md Stage 3) that exercises the LLM fallback
trigger, to pin down that it fires for exactly the right reason.
"""

from __future__ import annotations

from backend.tax_matcher.rules import classify_by_rules


def _txn(had_refund=False, gst_on_fee_flag=True, fee_amount=20.0, fee_amount_pending=False, txn_id="TXN00001"):
    return {
        "txn_id": txn_id,
        "had_refund": had_refund,
        "gst_on_fee_flag": gst_on_fee_flag,
        "fee_amount": fee_amount,
        "fee_amount_pending": fee_amount_pending,
    }


def test_refund_takes_precedence_over_everything():
    result = classify_by_rules(_txn(had_refund=True, gst_on_fee_flag=False, fee_amount=0.0))
    assert result.category == "refund_credit_note"
    assert result.method == "rule"


def test_exempt_when_gst_on_fee_flag_false():
    result = classify_by_rules(_txn(had_refund=False, gst_on_fee_flag=False, fee_amount=20.0))
    assert result.category == "exempt"


def test_gst_on_fee_when_fee_positive_and_flag_true():
    result = classify_by_rules(_txn(had_refund=False, gst_on_fee_flag=True, fee_amount=20.0))
    assert result.category == "gst_on_fee"


def test_taxable_sale_is_the_default():
    result = classify_by_rules(_txn(had_refund=False, gst_on_fee_flag=True, fee_amount=0.0))
    assert result.category == "taxable_sale"


def test_fee_amount_pending_declines_to_classify():
    # The genuine data-gap case: gateway hasn't computed the fee yet. All three
    # required fields are otherwise well-formed, but the rule engine must still
    # decline so the LLM fallback tier actually gets exercised.
    result = classify_by_rules(_txn(fee_amount_pending=True))
    assert result is None


def test_missing_required_field_declines_to_classify():
    txn = _txn()
    txn["fee_amount"] = None
    assert classify_by_rules(txn) is None

    txn2 = _txn()
    txn2["had_refund"] = None
    assert classify_by_rules(txn2) is None

    txn3 = _txn()
    txn3["gst_on_fee_flag"] = None
    assert classify_by_rules(txn3) is None


def test_malformed_fee_amount_declines_to_classify():
    txn = _txn()
    txn["fee_amount"] = "pending"  # wrong type, not just missing
    assert classify_by_rules(txn) is None


def test_reasoning_is_populated_for_every_resolved_category():
    for txn in (
        _txn(had_refund=True),
        _txn(gst_on_fee_flag=False),
        _txn(fee_amount=20.0),
        _txn(fee_amount=0.0),
    ):
        result = classify_by_rules(txn)
        assert result.reasoning
        assert result.txn_id == txn["txn_id"]
