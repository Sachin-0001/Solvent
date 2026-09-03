"""
Production GMV forecaster: feature construction (leakage), train, and
predict, using a synthetic in-memory transaction list (no DB dependency) so
this stays a fast, deterministic unit test — same style as the reconciliation
tests. Uses a temp model path so it never overwrites the real trained
artifact in ML/notebooks/artifacts/gmv.joblib.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

import backend.forecaster.gmv as gmv_module
from backend.forecaster.gmv import (
    GMV_FEATURES,
    GMV_TARGET,
    build_daily_gmv_frame,
    predict_next_day_gmv,
    train_gmv_model,
)


def _synthetic_transactions(n_days: int = 60, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    start = datetime(2025, 1, 1)
    txns = []
    for day in range(n_days):
        date = start + timedelta(days=day)
        n_txns = rng.randint(3, 8)
        for i in range(n_txns):
            txns.append(
                {
                    "txn_id": f"TXN{day:03d}{i}",
                    "created_at": (date + timedelta(hours=rng.randint(0, 23))).isoformat(),
                    "txn_amount": round(rng.uniform(100, 5000), 2),
                }
            )
    return txns


def test_feature_construction_does_not_leak_future_values():
    txns = _synthetic_transactions()
    daily = build_daily_gmv_frame(txns)

    # gmv_rolling_7 for day T must equal the mean of days [T-7, T-1] — i.e.
    # it must NOT include day T's own total_gmv.
    for i in range(8, len(daily)):
        window = daily["total_gmv"].iloc[i - 7 : i]  # days T-7..T-1
        expected = window.mean()
        actual = daily["gmv_rolling_7"].iloc[i]
        assert abs(actual - expected) < 1e-9

    # target_gmv for day T must equal day T+1's total_gmv, never day T's own.
    for i in range(len(daily) - 1):
        assert daily[GMV_TARGET].iloc[i] == daily["total_gmv"].iloc[i + 1]


def test_model_can_train_and_artifact_can_load(tmp_path, monkeypatch):
    model_path = tmp_path / "gmv_test.joblib"
    monkeypatch.setattr(gmv_module, "MODEL_PATH", model_path)

    txns = _synthetic_transactions()
    report = train_gmv_model(txns)

    assert report["method"] == "linear_regression"
    assert report["n_train"] > 0 and report["n_test"] > 0
    assert model_path.exists()

    import joblib

    loaded = joblib.load(model_path)
    assert hasattr(loaded, "predict")


def test_prediction_works_end_to_end(tmp_path, monkeypatch):
    model_path = tmp_path / "gmv_test.joblib"
    monkeypatch.setattr(gmv_module, "MODEL_PATH", model_path)
    gmv_module._model_cache = None

    txns = _synthetic_transactions()
    train_gmv_model(txns)
    gmv_module._model_cache = None  # force reload from the temp path

    result = predict_next_day_gmv(txns)
    assert result["method"] == "linear_regression"
    assert result["model"] == "gmv"
    assert isinstance(result["value"], float)
    assert result["forecast_date"] is not None
