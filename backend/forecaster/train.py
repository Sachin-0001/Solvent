"""
Step 4 entry point. Run with: python -m backend.forecaster.train

Trains Model A (days_to_settle) and Model B (deduction_pct) independently — both
run for every transaction, there is no router between them. For each: fit the
scikit-learn linear regression baseline, inspect residuals against txn_amount for
curvature, and only if that curvature is clear, also fit a degree-2 polynomial
variant on txn_amount and keep whichever validates better on held-out MAE.
Reports MAE/MAPE for both models — this is the gate before step 5.
"""

from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from backend import db
from backend.config import MODELS_DIR
from backend.forecaster.gmv import train_gmv_model
from backend.forecaster.features import (
    MODEL_A_CATEGORICAL,
    MODEL_A_NUMERIC,
    MODEL_A_TARGET,
    MODEL_B_FEE_CATEGORICAL,
    MODEL_B_FEE_NUMERIC,
    MODEL_B_FEE_TARGET,
    MODEL_B_REFUND_CATEGORICAL,
    MODEL_B_REFUND_NUMERIC,
    MODEL_B_REFUND_TARGET,
    build_pipeline,
    to_frame,
)

RANDOM_STATE = 42
TEST_SIZE = 0.2


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    nonzero = np.abs(y_true) > 1e-6
    if not nonzero.any():
        return float("nan")
    return float(np.mean(np.abs((y_true[nonzero] - y_pred[nonzero]) / y_true[nonzero])) * 100)


def _mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


def _has_curvature(pipeline, X_train: pd.DataFrame, y_train: pd.Series) -> bool:
    """Fits the linear baseline, then checks whether residuals still correlate
    with txn_amount^2 — a simple, honest signal for curvature the linear model
    is missing, rather than trying polynomial features unconditionally."""
    residuals = y_train.values - pipeline.predict(X_train)
    amount = X_train["txn_amount"].values
    amount_sq = amount**2
    if np.std(amount_sq) < 1e-9 or np.std(residuals) < 1e-9:
        return False
    corr = np.corrcoef(residuals, amount_sq)[0, 1]
    return bool(np.abs(corr) > 0.15)


def _fit_and_report(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
    numeric: list[str],
    categorical: list[str],
    target: str,
    label: str,
) -> tuple[dict, object]:
    baseline = build_pipeline(numeric, categorical, amount_poly_degree=1)
    baseline.fit(X_train, y_train)
    baseline_pred = baseline.predict(X_test)
    baseline_mae = _mae(y_test, baseline_pred)
    baseline_mape = _mape(y_test, baseline_pred)

    curvature = _has_curvature(baseline, X_train, y_train)
    best_pipeline = baseline
    best_mae, best_mape = baseline_mae, baseline_mape
    chosen = "linear"

    poly_mae = poly_mape = None
    if curvature:
        poly = build_pipeline(numeric, categorical, amount_poly_degree=2)
        poly.fit(X_train, y_train)
        poly_pred = poly.predict(X_test)
        poly_mae = _mae(y_test, poly_pred)
        poly_mape = _mape(y_test, poly_pred)
        if poly_mae < baseline_mae:
            best_pipeline, best_mae, best_mape, chosen = poly, poly_mae, poly_mape, "polynomial(degree=2)"

    # Refit the chosen model on train+test combined for the artifact we actually ship.
    X_full = pd.concat([X_train, X_test])
    y_full = pd.concat([y_train, y_test])
    best_pipeline.fit(X_full, y_full)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / f"{label}.joblib"
    joblib.dump(best_pipeline, model_path)

    report = {
        "label": label,
        "target": target,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "curvature_detected": curvature,
        "baseline_linear": {"mae": round(baseline_mae, 4), "mape_pct": round(baseline_mape, 2)},
        "polynomial_degree2": (
            {"mae": round(poly_mae, 4), "mape_pct": round(poly_mape, 2)} if poly_mae is not None else None
        ),
        "chosen_model": chosen,
        "chosen_mae": round(best_mae, 4),
        "chosen_mape_pct": round(best_mape, 2),
        "model_path": str(model_path),
    }
    return report, best_pipeline


def train_and_evaluate(
    df: pd.DataFrame,
    numeric: list[str],
    categorical: list[str],
    target: str,
    label: str,
) -> dict:
    X = df[numeric + categorical]
    y = df[target]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )
    report, _ = _fit_and_report(X_train, X_test, y_train, y_test, numeric, categorical, target, label)
    return report


def train_model_b(df: pd.DataFrame) -> tuple[dict, dict, dict]:
    """
    Model B is split into two additive components (see features.py for why):
    fee_deduction_pct (every transaction) and refund_deduction_pct (trained
    only on had_refund=1 rows, so the ~92% zero rows don't dilute it). Both
    share one overall train/test split of the full dataset so a combined
    total_deduction_pct = fee_pred + refund_pred (gated by had_refund) can be
    evaluated on the same held-out rows the original single Model B was
    scored on — the number to compare directly against the old 0.0316 MAE /
    126.83% MAPE.
    """
    df_train, df_test = train_test_split(df, test_size=TEST_SIZE, random_state=RANDOM_STATE)

    fee_report, fee_pipeline = _fit_and_report(
        df_train[MODEL_B_FEE_NUMERIC + MODEL_B_FEE_CATEGORICAL],
        df_test[MODEL_B_FEE_NUMERIC + MODEL_B_FEE_CATEGORICAL],
        df_train[MODEL_B_FEE_TARGET],
        df_test[MODEL_B_FEE_TARGET],
        MODEL_B_FEE_NUMERIC,
        MODEL_B_FEE_CATEGORICAL,
        MODEL_B_FEE_TARGET,
        "model_b_fee_deduction_pct",
    )

    refund_train_df = df_train[df_train["had_refund"] == 1]
    refund_test_df = df_test[df_test["had_refund"] == 1]
    refund_report, refund_pipeline = _fit_and_report(
        refund_train_df[MODEL_B_REFUND_NUMERIC + MODEL_B_REFUND_CATEGORICAL],
        refund_test_df[MODEL_B_REFUND_NUMERIC + MODEL_B_REFUND_CATEGORICAL],
        refund_train_df[MODEL_B_REFUND_TARGET],
        refund_test_df[MODEL_B_REFUND_TARGET],
        MODEL_B_REFUND_NUMERIC,
        MODEL_B_REFUND_CATEGORICAL,
        MODEL_B_REFUND_TARGET,
        "model_b_refund_deduction_pct",
    )
    refund_report["n_train_full_test_set"] = len(df_test)
    refund_report["note"] = (
        "n_train/n_test above count only had_refund=1 rows (the model's actual "
        "training/eval population); n_train_full_test_set is the overall test "
        "split size used for the combined total_deduction_pct evaluation below."
    )

    fee_pred_test = fee_pipeline.predict(df_test[MODEL_B_FEE_NUMERIC + MODEL_B_FEE_CATEGORICAL])
    refund_pred_test = np.where(
        df_test["had_refund"].values == 1,
        refund_pipeline.predict(df_test[MODEL_B_REFUND_NUMERIC + MODEL_B_REFUND_CATEGORICAL]),
        0.0,
    )
    total_pred_test = fee_pred_test + refund_pred_test
    total_actual_test = df_test["deduction_pct"].values
    combined_report = {
        "label": "model_b_combined_total_deduction_pct",
        "target": "deduction_pct (fee_deduction_pct + refund_deduction_pct)",
        "n_test": len(df_test),
        "mae": round(_mae(total_actual_test, total_pred_test), 4),
        "mape_pct": round(_mape(total_actual_test, total_pred_test), 2),
    }
    return fee_report, refund_report, combined_report


def main() -> None:
    transactions = db.load_base_transactions()
    df = to_frame(transactions)

    report_a = train_and_evaluate(
        df, MODEL_A_NUMERIC, MODEL_A_CATEGORICAL, MODEL_A_TARGET, "model_a_days_to_settle"
    )
    report_b_fee, report_b_refund, report_b_combined = train_model_b(df)
    report_gmv = train_gmv_model(transactions)

    print("=== Forecaster training report ===\n")
    for report in (report_a, report_b_fee, report_b_refund):
        print(f"--- {report['label']} (target: {report['target']}) ---")
        print(f"n_train={report['n_train']}  n_test={report['n_test']}")
        print(f"Curvature detected on txn_amount: {report['curvature_detected']}")
        print(f"  Linear baseline    -> MAE: {report['baseline_linear']['mae']}  MAPE: {report['baseline_linear']['mape_pct']}%")
        if report["polynomial_degree2"]:
            print(f"  Polynomial deg=2   -> MAE: {report['polynomial_degree2']['mae']}  MAPE: {report['polynomial_degree2']['mape_pct']}%")
        print(f"  CHOSEN: {report['chosen_model']} -> MAE: {report['chosen_mae']}  MAPE: {report['chosen_mape_pct']}%")
        print(f"  Saved: {report['model_path']}\n")

    print(f"--- {report_b_combined['label']} ---")
    print(f"n_test={report_b_combined['n_test']}")
    print(f"  COMBINED (fee + refund, gated by had_refund) -> "
          f"MAE: {report_b_combined['mae']}  MAPE: {report_b_combined['mape_pct']}%")
    print("  (compare directly against the old single-model Model B: MAE 0.0316 / MAPE 126.83%)\n")

    print("--- gmv (target: next-day total GMV) ---")
    print(f"n_train={report_gmv['n_train']}  n_test={report_gmv['n_test']}")
    print(f"  Linear regression  -> MAE: {report_gmv['mae']}  RMSE: {report_gmv['rmse']}")
    print(f"  Naive (prev day)   -> MAE: {report_gmv['naive_mae']}")
    print(f"  Improvement over naive: {report_gmv['improvement_pct']}%")
    print(f"  Saved: {report_gmv['model_path']}\n")

    db.save_forecaster_metrics("model_a", report_a)
    db.save_forecaster_metrics("model_b_fee", report_b_fee)
    db.save_forecaster_metrics("model_b_refund", report_b_refund)
    db.save_forecaster_metrics("model_b_combined", report_b_combined)
    db.save_forecaster_metrics("gmv", report_gmv)
    print("Wrote (Postgres): forecaster_metrics (model_a, model_b_fee, model_b_refund, model_b_combined, gmv)")


if __name__ == "__main__":
    main()
