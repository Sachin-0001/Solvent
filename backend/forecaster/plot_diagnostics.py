"""
Analysis-only script (not part of the pipeline: not imported by train.py,
predict.py, or api.py). Run with: python -m backend.forecaster.plot_diagnostics

Model A and Model B are both plain scikit-learn `LinearRegression` fit via the
closed-form normal-equation solver (see features.py's `build_pipeline`) — there
is no gradient descent, no epochs, and therefore no loss-vs-epoch curve to
plot. Producing one would mean fabricating iterations that never happened.

Instead this script generates the honest diagnostic equivalents, reusing the
exact train/test split (random_state=42, test_size=0.2) and pipeline
construction from train.py so every number here is reproducible against
docs/metrics.md:

  1. A learning curve (train-set size vs held-out MAE) — the real analogue of
     a "loss curve" for a closed-form model: it shows error as a function of
     how much data the model has seen, via repeated cross-validated refits at
     increasing training sizes, rather than iterations of one fit.
  2. Predicted vs. actual on the held-out test split.
  3. Residuals vs. txn_amount — the same curvature diagnostic train.py's
     `_has_curvature` already computes a correlation for; this plots it.
  4. Residual distribution (histogram).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.model_selection import learning_curve, train_test_split

from backend import db
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
from backend.forecaster.train import RANDOM_STATE, TEST_SIZE

FIGURES_DIR = Path(__file__).resolve().parents[2] / "docs" / "figures"

plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#333333",
        "axes.grid": True,
        "grid.color": "#e5e5e5",
        "grid.linewidth": 0.6,
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
    }
)

ACCENT = "#2bd6a3"
ACCENT_2 = "#5b8def"
ACCENT_BAD = "#f04f61"


def _split(df, numeric, categorical, target):
    X = df[numeric + categorical]
    y = df[target]
    return train_test_split(X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE)


def plot_model(df, numeric, categorical, target, label, title):
    X_train, X_test, y_train, y_test = _split(df, numeric, categorical, target)
    pipeline = build_pipeline(numeric, categorical, amount_poly_degree=1)

    # 1. Learning curve: MAE at increasing training-set sizes, 5-fold CV on
    # the training split only (test split stays untouched, matching train.py).
    train_sizes, train_scores, val_scores = learning_curve(
        pipeline,
        X_train,
        y_train,
        train_sizes=np.linspace(0.2, 1.0, 8),
        cv=5,
        scoring="neg_mean_absolute_error",
        random_state=RANDOM_STATE,
    )
    train_mae = -train_scores.mean(axis=1)
    val_mae = -val_scores.mean(axis=1)

    # 2 & 3. Fit once on the actual train split (same as train.py) for the
    # held-out predictions and residual diagnostics.
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    residuals = y_test.values - y_pred
    amount = X_test["txn_amount"].values

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    fig.suptitle(title, fontsize=14, fontweight="bold")

    ax = axes[0, 0]
    ax.plot(train_sizes, train_mae, "o-", color=ACCENT_2, label="Train MAE")
    ax.plot(train_sizes, val_mae, "o-", color=ACCENT, label="Cross-val MAE")
    ax.set_xlabel("Training examples")
    ax.set_ylabel(f"MAE ({target})")
    ax.set_title("Learning curve (no epochs — closed-form OLS)")
    ax.legend(frameon=False)

    ax = axes[0, 1]
    lo = min(y_test.min(), y_pred.min())
    hi = max(y_test.max(), y_pred.max())
    ax.plot([lo, hi], [lo, hi], "--", color="#999999", linewidth=1)
    ax.scatter(y_test, y_pred, s=18, color=ACCENT_2, alpha=0.7, edgecolors="none")
    ax.set_xlabel(f"Actual {target}")
    ax.set_ylabel(f"Predicted {target}")
    ax.set_title("Predicted vs. actual (held-out test)")

    ax = axes[1, 0]
    ax.axhline(0, color="#999999", linewidth=1)
    ax.scatter(amount, residuals, s=18, color=ACCENT, alpha=0.7, edgecolors="none")
    ax.set_xlabel("txn_amount")
    ax.set_ylabel("Residual (actual - predicted)")
    corr = np.corrcoef(residuals, amount**2)[0, 1] if np.std(amount) > 0 else 0.0
    ax.set_title(f"Residuals vs. txn_amount  (corr w/ amount² = {corr:.3f})")

    ax = axes[1, 1]
    ax.hist(residuals, bins=20, color=ACCENT_2, alpha=0.85, edgecolor="white")
    ax.axvline(0, color=ACCENT_BAD, linewidth=1.2, linestyle="--")
    ax.set_xlabel("Residual")
    ax.set_ylabel("Count")
    ax.set_title("Residual distribution")

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FIGURES_DIR / f"{label}_diagnostics.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved {out_path}")
    return {
        "final_train_mae": round(float(train_mae[-1]), 4),
        "final_val_mae": round(float(val_mae[-1]), 4),
        "residual_amount_sq_corr": round(float(corr), 4),
    }


def main() -> None:
    transactions = db.load_base_transactions()
    df = to_frame(transactions)
    df_refund_only = df[df["had_refund"] == 1]

    summary = {}
    summary["model_a"] = plot_model(
        df,
        MODEL_A_NUMERIC,
        MODEL_A_CATEGORICAL,
        MODEL_A_TARGET,
        "model_a_days_to_settle",
        "Model A — days_to_settle (linear regression)",
    )
    summary["model_b_fee"] = plot_model(
        df,
        MODEL_B_FEE_NUMERIC,
        MODEL_B_FEE_CATEGORICAL,
        MODEL_B_FEE_TARGET,
        "model_b_fee_deduction_pct",
        "Model B (fee) — fee_deduction_pct (linear regression)",
    )
    summary["model_b_refund"] = plot_model(
        df_refund_only,
        MODEL_B_REFUND_NUMERIC,
        MODEL_B_REFUND_CATEGORICAL,
        MODEL_B_REFUND_TARGET,
        "model_b_refund_deduction_pct",
        "Model B (refund) — refund_deduction_pct, had_refund=1 rows only (linear regression)",
    )

    print("\n=== Diagnostic summary ===")
    for label, stats in summary.items():
        print(f"{label}: {stats}")


if __name__ == "__main__":
    main()
