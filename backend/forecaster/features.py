"""
Shared feature-pipeline construction for both forecaster models. Pure
scikit-learn — no LLM, no other ML family. `build_pipeline` lets each model
opt into polynomial features on txn_amount only when residuals justify it
(see model_a_settlement_time.py / model_b_deduction.py), while categorical
columns always go through one-hot encoding untouched.
"""

from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, PolynomialFeatures

MODEL_A_NUMERIC = ["txn_amount", "day_of_week", "is_weekend_or_holiday", "had_dispute_flag"]
MODEL_A_CATEGORICAL = ["payment_method", "merchant_category"]
MODEL_A_TARGET = "days_to_settle"

# Model B was originally one linear model on deduction_pct, whose true target
# is bimodal (correlation with had_refund = 0.95 — see
# docs/forecaster_diagnostics.md) and drove a 126.83% MAPE. Split into two
# additive components that are each well-behaved on their own:
#   fee_deduction_pct    = (fee_amount + tax_on_fee) / txn_amount  — every txn
#   refund_deduction_pct = refund_amount / txn_amount              — 0 unless had_refund
# total_deduction_pct = fee_deduction_pct + refund_deduction_pct, combined at
# inference time (see predict.py). refund_amount/had_refund are dropped from
# the fee model's features (they're causally irrelevant to the fee portion);
# the refund model is trained only on had_refund=1 rows so it isn't diluted
# by the ~92% of rows where the target is trivially zero.
MODEL_B_FEE_NUMERIC = ["txn_amount", "gst_on_fee_flag"]
MODEL_B_FEE_CATEGORICAL = ["payment_method"]
MODEL_B_FEE_TARGET = "fee_deduction_pct"

MODEL_B_REFUND_NUMERIC = ["txn_amount", "refund_amount"]
MODEL_B_REFUND_CATEGORICAL = ["payment_method"]
MODEL_B_REFUND_TARGET = "refund_deduction_pct"


def build_pipeline(
    numeric_features: list[str],
    categorical_features: list[str],
    amount_poly_degree: int = 1,
) -> Pipeline:
    """
    `amount_poly_degree` > 1 expands txn_amount into polynomial terms (fit only
    if residual inspection shows clear curvature against txn_amount); every
    other numeric feature stays linear, and categoricals are always one-hot.
    """
    other_numeric = [f for f in numeric_features if f != "txn_amount"]

    amount_transformer = Pipeline(
        [("poly", PolynomialFeatures(degree=amount_poly_degree, include_bias=False))]
    )

    transformers = [("amount", amount_transformer, ["txn_amount"])]
    if other_numeric:
        # Plain "passthrough" doesn't declare matching output feature names in
        # every sklearn version, which trips ColumnTransformer's internal
        # name-consistency check when the input is a DataFrame. An explicit
        # one-to-one FunctionTransformer avoids depending on that version quirk.
        transformers.append(
            ("numeric", FunctionTransformer(feature_names_out="one-to-one"), other_numeric)
        )
    if categorical_features:
        transformers.append(
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical_features)
        )

    preprocessor = ColumnTransformer(transformers)
    return Pipeline([("preprocess", preprocessor), ("model", LinearRegression())])


def to_frame(transactions: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(transactions)
    for col in ("is_weekend_or_holiday", "had_dispute_flag", "had_refund", "gst_on_fee_flag"):
        if col in df.columns:
            df[col] = df[col].astype(int)
    if "fee_amount" in df.columns and "tax_on_fee" in df.columns:
        df["fee_deduction_pct"] = (df["fee_amount"] + df["tax_on_fee"]) / df["txn_amount"]
    if "refund_amount" in df.columns:
        # refund_amount is exactly 0 for had_refund=0 rows by construction
        # (synthetic_data_generator.py), so this is naturally 0 there too.
        df["refund_deduction_pct"] = df["refund_amount"] / df["txn_amount"]
    return df
