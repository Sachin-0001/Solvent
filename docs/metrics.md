# Solvent — Validation Metrics

## Stage 2: Reconciliation engine

Run: `python -m backend.reconciliation.run_reconciliation`
Validated against `backend/data/ground_truth.json` (257 transactions: 7 real
Razorpay test-mode payments + 250 synthetic, with deliberately injected
rounding/timestamp-drift/missing/duplicate mismatches across the synthetic
ledger and bank statement).

| Metric | Value |
|---|---|
| Precision | 1.0000 |
| Recall | 1.0000 |
| Match rate (matches / total ground-truth txns) | 0.9183 (236/257) |
| True positives | 236 |
| False positives | 0 |
| False negatives | 0 |
| Matches by tier | exact: 180, fuzzy: 56, llm: 0 |
| Honest exceptions (unresolved rows) | 54 |

**Why match rate (91.8%) is below 100% while precision/recall are 100%:** 21 of
257 ground-truth transactions have a genuinely missing row on one or both sides
(that's the point of the injected "missing" mismatch kind) — there is no correct
match to find. The engine correctly leaves all of them, plus the extra copies
from injected duplicates, in the exception list rather than forcing a false
match. Precision/recall are computed only over pairs the engine actually
reported, which is why they hit 1.0 exactly: every match it reported was
correct, and every should-reconcile pair got found.

**LLM tier resolved 0 of the 257** — exact and fuzzy match, given the ledger's
own fee/GST/refund figures, handled the entire reconcilable set numerically.
This is intentional per the "minimize LLM calls" rule; the LLM tier exists for
harder real-world cases and is exercised here purely for the *exception
reasoning* on the 54 unresolved rows. The reason-label breakdown depends on
the LLM's live output for that run (e.g. `missing_counterpart` /
`likely_duplicate` / `unexplained` when the LLM call doesn't return a
confident resolution) — check `/api/reconciliation/exceptions` or the
dashboard's Exception Ledger for the current run's actual split rather than a
number recorded here, since it can vary between reconciliation runs.

## Stage 4: Forecaster

Run: `python -m backend.forecaster.train`
Both models are plain scikit-learn `LinearRegression` on tabular features
(no polynomial curvature detected for either target), validated on a held-out
split of the 257-transaction dataset (`n_train=205, n_test=52`).

| Model | Target | MAE | MAPE | Model |
|---|---|---|---|---|
| A | `days_to_settle` | 0.5951 days | 30.3% | linear |
| B | `deduction_pct` | 0.0316 | 126.83% | linear |

**Model B's MAPE (126.83%) is the honest weak spot in the pipeline.** MAE is
low in absolute terms (±0.0316 of a 0-1 deduction fraction), but MAPE blows up
because many transactions have a near-zero true `deduction_pct` — a small
absolute error becomes a huge percentage error when the denominator is close
to zero. This is reported as-is per the "no hidden exceptions" rule; the
dashboard's forecast panel surfaces both numbers (Model B's MAPE flagged)
rather than only the more flattering MAE.

**See [`forecaster_diagnostics.md`](forecaster_diagnostics.md)** for learning
curves, predicted-vs-actual, and residual plots for both models, plus the
root-cause analysis of *why* Model B's MAPE is high (short version:
`deduction_pct` is bimodal — driven 0.95-correlated by `had_refund` — and a
single linear model can't fully capture the variance within the refunded
group).
