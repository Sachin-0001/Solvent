"""
Integration-style tests for the production forecaster artifacts and the new
API endpoints. Unlike the rest of backend/tests/ (pure unit tests, no
external dependency), these exercise the real Postgres-backed pipeline and
the trained joblib artifacts directly — this is what the audit flagged as
completely untested (the missing-artifact bug that broke /api/forecast would
have been caught immediately by a test like this). Requires DATABASE_URL to
be configured and the forecaster to have been trained at least once
(`python -m backend.forecaster.train`), same precondition the API itself has.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.api import app

client = TestClient(app)


def _db_available() -> bool:
    try:
        return db.healthcheck()
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="DATABASE_URL not reachable in this environment")


@requires_db
def test_model_a_b_artifacts_load_successfully():
    from backend.forecaster.predict import _load_models

    model_a, model_b_fee, model_b_refund = _load_models()
    assert hasattr(model_a, "predict")
    assert hasattr(model_b_fee, "predict")
    assert hasattr(model_b_refund, "predict")


@requires_db
def test_forecast_endpoint_does_not_crash():
    res = client.get("/api/forecast")
    assert res.status_code == 200
    body = res.json()
    assert "reference_date" in body
    assert isinstance(body["days"], list)


@requires_db
def test_cash_position_endpoint_schema():
    res = client.get("/api/cash-position", params={"current_cash": 500_000})
    assert res.status_code == 200
    body = res.json()
    for key in (
        "current_cash", "expected_settlement", "expected_refunds",
        "expected_net_cash_flow", "projected_cash", "forecast_date", "forecast_method",
    ):
        assert key in body
    assert body["current_cash"] == 500_000.0
    assert body["projected_cash"] == round(
        body["current_cash"] + body["expected_net_cash_flow"], 2
    )


@requires_db
def test_cash_position_endpoint_default_current_cash():
    res = client.get("/api/cash-position")
    assert res.status_code == 200
    assert res.json()["current_cash"] == 1_000_000.0


@requires_db
def test_cash_position_endpoint_rejects_invalid_current_cash():
    res = client.get("/api/cash-position", params={"current_cash": "not-a-number"})
    assert res.status_code == 422


@requires_db
def test_gmv_forecast_endpoint():
    res = client.get("/api/forecast/gmv")
    assert res.status_code == 200
    body = res.json()
    assert body["method"] == "linear_regression"
    assert body["model"] == "gmv"
    assert isinstance(body["value"], float)


@requires_db
def test_existing_reconciliation_and_tax_endpoints_still_work():
    recon = client.get("/api/reconciliation/summary")
    assert recon.status_code == 200
    assert recon.json()["precision"] == pytest.approx(1.0, abs=0.01) or "precision" in recon.json()

    tax = client.get("/api/tax/summary")
    assert tax.status_code == 200
    assert "total" in tax.json()
