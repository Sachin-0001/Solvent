"""
Production daily-GMV forecaster — Track 4's operational cash-position input,
separate from Model A/B (per-transaction days_to_settle/deduction_pct).

Validated in ML/notebooks/model_a_days_to_settle_training.ipynb against
ML/data/base_transactions.csv (LinearRegression MAE ~87,993.95 vs. naive
~115,860.80, chronological 80/20 split). This module reproduces that exact
feature recipe against the application's own data source (Postgres via
`backend.db`, not the notebook CSV) so training and inference share one
feature-construction path — `build_daily_gmv_frame` is called by both
`train_gmv_model` (this file) and `predict_next_day_gmv` (below).

Features (all computed with `shift(1)` before any rolling window, so no
feature for day T uses GMV/txn_count observed on day T or later):
  gmv_lag_1, gmv_lag_7, gmv_rolling_7, gmv_rolling_30,
  txn_count_lag_1, txn_count_lag_7, txn_count_rolling_7, is_weekend
Target: next day's total GMV (`total_gmv.shift(-1)`).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

from backend.config import MODELS_DIR

GMV_FEATURES = [
    "gmv_lag_1",
    "gmv_lag_7",
    "gmv_rolling_7",
    "gmv_rolling_30",
    "txn_count_lag_1",
    "txn_count_lag_7",
    "txn_count_rolling_7",
    "is_weekend",
]
GMV_TARGET = "target_gmv"
TEST_SIZE = 0.2

MODEL_PATH = MODELS_DIR / "gmv.joblib"


def _parse_naive(dt_str: str) -> datetime:
    dt = datetime.fromisoformat(dt_str)
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def build_daily_gmv_frame(transactions: list[dict[str, Any]]) -> pd.DataFrame:
    """One row per calendar day with same-day totals, lag/rolling features
    (all shifted before windowing, so day T's features never see day T's or
    any later day's GMV), and next-day target. Rows without a full feature
    set (the first 30 days, and the last day with no next-day target) are
    dropped — the same `dropna()` the validated notebook applies."""
    df = pd.DataFrame(transactions)
    df["created_at"] = df["created_at"].apply(_parse_naive)
    df["date"] = df["created_at"].dt.date

    daily = (
        df.groupby("date")
        .agg(total_gmv=("txn_amount", "sum"), txn_count=("txn_amount", "count"))
        .reset_index()
    )
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values("date").reset_index(drop=True)

    daily["is_weekend"] = (daily["date"].dt.dayofweek >= 5).astype(int)

    daily["gmv_lag_1"] = daily["total_gmv"].shift(1)
    daily["gmv_lag_7"] = daily["total_gmv"].shift(7)
    daily["gmv_rolling_7"] = daily["total_gmv"].shift(1).rolling(7).mean()
    daily["gmv_rolling_30"] = daily["total_gmv"].shift(1).rolling(30).mean()

    daily["txn_count_lag_1"] = daily["txn_count"].shift(1)
    daily["txn_count_lag_7"] = daily["txn_count"].shift(7)
    daily["txn_count_rolling_7"] = daily["txn_count"].shift(1).rolling(7).mean()

    daily[GMV_TARGET] = daily["total_gmv"].shift(-1)

    return daily


def train_gmv_model(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Chronological 80/20 split (no shuffling — this is a time series), plain
    LinearRegression, compared against the naive same-value baseline. Saves
    the fitted model (refit on the full usable frame) to MODEL_PATH."""
    daily = build_daily_gmv_frame(transactions).dropna(subset=GMV_FEATURES + [GMV_TARGET])

    X = daily[GMV_FEATURES]
    y = daily[GMV_TARGET]
    split = int(len(X) * (1 - TEST_SIZE))
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    model = LinearRegression()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    mae = float(mean_absolute_error(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

    naive_pred = daily["total_gmv"].iloc[split:].values
    naive_mae = float(mean_absolute_error(y_test, naive_pred))
    improvement_pct = round((naive_mae - mae) / naive_mae * 100, 2) if naive_mae else None

    # Refit on the full usable frame for the artifact actually shipped.
    model.fit(X, y)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    return {
        "label": "gmv",
        "target": GMV_TARGET,
        "method": "linear_regression",
        "n_train": len(X_train),
        "n_test": len(X_test),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "naive_mae": round(naive_mae, 2),
        "improvement_pct": improvement_pct,
        "model_path": str(MODEL_PATH),
    }


_model_cache: LinearRegression | None = None


def _load_model() -> LinearRegression:
    global _model_cache
    if _model_cache is None:
        _model_cache = joblib.load(MODEL_PATH)
    return _model_cache


def predict_next_day_gmv(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Predicts tomorrow's GMV from the most recent complete day's features.
    Raises FileNotFoundError with a clear message if the model hasn't been
    trained yet — never silently falls back to a fabricated number."""
    daily = build_daily_gmv_frame(transactions)
    usable = daily.dropna(subset=GMV_FEATURES)
    if usable.empty:
        raise ValueError("Not enough daily history to build GMV features (need 30+ days).")

    latest = usable.iloc[[-1]]
    model = _load_model()
    prediction = float(model.predict(latest[GMV_FEATURES])[0])
    last_date = latest["date"].iloc[0]
    forecast_date = (last_date + timedelta(days=1)).date().isoformat()

    return {
        "value": round(prediction, 2),
        "method": "linear_regression",
        "model": "gmv",
        "forecast_date": forecast_date,
        "based_on_date": last_date.date().isoformat(),
    }


__all__ = [
    "GMV_FEATURES",
    "GMV_TARGET",
    "build_daily_gmv_frame",
    "train_gmv_model",
    "predict_next_day_gmv",
]
