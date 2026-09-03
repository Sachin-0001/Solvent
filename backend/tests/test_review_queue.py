"""
Human-in-the-loop review queue: the API surface and the persistence
guarantees that make it an audit trail rather than a scratch pad.

These hit the real Postgres (like test_forecast_and_cash_api.py) because the
properties worth pinning here are storage properties — that a decision
survives, that re-deciding replaces rather than duplicates, and that reviews
key off (row_id, side) instead of the exceptions table's surrogate id, which
is reassigned on every pipeline refresh.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.api import app

client = TestClient(app)

REVIEW_ROW_ID = "__test_review_row__"
REVIEW_SIDE = "ledger"


def _db_available() -> bool:
    try:
        return db.healthcheck()
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_available(), reason="DATABASE_URL not reachable in this environment"
)


@pytest.fixture(autouse=True)
def _cleanup():
    """Removes the synthetic review rows these tests create, so they never
    leak into the real queue the dashboard renders."""
    yield
    if _db_available():
        db.delete_reconciliation_review(REVIEW_ROW_ID, REVIEW_SIDE)


@requires_db
def test_review_queue_returns_pending_and_resolved_counts():
    res = client.get("/api/reconciliation/review-queue")
    assert res.status_code == 200
    body = res.json()
    for key in ("total", "pending", "resolved", "items"):
        assert key in body
    # Every exception is either awaiting a decision or has one — nothing falls
    # through the cracks unaccounted for.
    assert body["pending"] + body["resolved"] == body["total"]


@requires_db
def test_queue_items_carry_the_evidence_needed_to_decide():
    body = client.get("/api/reconciliation/review-queue").json()
    if not body["items"]:
        pytest.skip("no exceptions in the current dataset")
    item = body["items"][0]
    # A reviewer can't judge a pairing without the row itself and the
    # candidate counterparts, so both must be present in the payload.
    assert "source_row" in item
    assert isinstance(item["candidates"], list)
    assert "review" in item


@requires_db
def test_decision_persists_and_is_readable_back():
    saved = db.save_reconciliation_review(
        row_id=REVIEW_ROW_ID,
        side=REVIEW_SIDE,
        decision="written_off",
        order_id="order_test",
        note="no counterpart in the statement window",
        reviewer="pytest",
    )
    assert saved["decision"] == "written_off"
    assert saved["decided_at"]

    stored = [
        r
        for r in db.load_reconciliation_reviews()
        if r["row_id"] == REVIEW_ROW_ID and r["side"] == REVIEW_SIDE
    ]
    assert len(stored) == 1
    assert stored[0]["note"] == "no counterpart in the statement window"
    assert stored[0]["reviewer"] == "pytest"


@requires_db
def test_re_deciding_replaces_rather_than_duplicating():
    """A reviewer correcting themselves must not leave two contradictory
    records for the same row."""
    db.save_reconciliation_review(REVIEW_ROW_ID, REVIEW_SIDE, "written_off")
    db.save_reconciliation_review(REVIEW_ROW_ID, REVIEW_SIDE, "approved_match")

    stored = [
        r
        for r in db.load_reconciliation_reviews()
        if r["row_id"] == REVIEW_ROW_ID and r["side"] == REVIEW_SIDE
    ]
    assert len(stored) == 1
    assert stored[0]["decision"] == "approved_match"


@requires_db
def test_reopening_removes_the_decision():
    db.save_reconciliation_review(REVIEW_ROW_ID, REVIEW_SIDE, "written_off")
    db.delete_reconciliation_review(REVIEW_ROW_ID, REVIEW_SIDE)
    stored = [r for r in db.load_reconciliation_reviews() if r["row_id"] == REVIEW_ROW_ID]
    assert stored == []


@requires_db
def test_api_rejects_an_unknown_decision():
    res = client.post(
        "/api/reconciliation/review",
        json={"row_id": REVIEW_ROW_ID, "side": REVIEW_SIDE, "decision": "looks_fine_to_me"},
    )
    assert res.status_code == 400


@requires_db
def test_api_requires_a_counterpart_for_manual_pairing():
    """"Manually paired" without naming the counterpart is meaningless, and
    silently accepting it would record a decision that can't be audited."""
    res = client.post(
        "/api/reconciliation/review",
        json={"row_id": REVIEW_ROW_ID, "side": REVIEW_SIDE, "decision": "manually_paired"},
    )
    assert res.status_code == 400


@requires_db
def test_api_round_trip_moves_an_item_from_pending_to_resolved():
    res = client.post(
        "/api/reconciliation/review",
        json={
            "row_id": REVIEW_ROW_ID,
            "side": REVIEW_SIDE,
            "decision": "manually_paired",
            "paired_row_id": "BANK99999",
            "reviewer": "pytest",
        },
    )
    assert res.status_code == 200
    assert res.json()["paired_row_id"] == "BANK99999"

    reopened = client.delete(
        f"/api/reconciliation/review?row_id={REVIEW_ROW_ID}&side={REVIEW_SIDE}"
    )
    assert reopened.status_code == 200
    assert reopened.json()["reopened"] is True


@requires_db
def test_reviews_survive_a_pipeline_full_refresh():
    """Every other derived table is TRUNCATE+reinserted per run. A reviewer's
    decision is a record of something a person did, so re-running ingestion
    must not erase it — this is the guarantee that makes it an audit trail."""
    db.save_reconciliation_review(REVIEW_ROW_ID, REVIEW_SIDE, "written_off", reviewer="pytest")

    # Re-save the exceptions table exactly as the pipeline does.
    existing = db.load_reconciliation_exceptions()
    db.save_reconciliation_exceptions(existing)

    stored = [r for r in db.load_reconciliation_reviews() if r["row_id"] == REVIEW_ROW_ID]
    assert len(stored) == 1, "review was wiped by the exceptions full-refresh"
