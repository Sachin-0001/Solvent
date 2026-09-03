# Solvent - Validation Metrics

## Stage 1: Ingestion - Track A purity

Run: `python -m backend.ingestion.run_ingestion`

The scored batch (`ground_truth.json` and everything downstream) is now **100%
synthetic** - 250 base transactions, every one with a genuinely known
ground-truth label. The 7 real Razorpay test-mode payments previously blended
into this set have been moved to a separate calibration-only step
(`fetch_calibration_transactions` in `run_ingestion.py`), written to
`backend/data/raw/razorpay_calibration.json` for manual reference and never
read by `generate_base_transactions` or any downstream stage. A real
payment's true reconciliation/tax/forecast labels aren't independently
knowable the way an injected synthetic label is, so blending them in made
those 7 ground-truth entries assumed-correct rather than known-correct -
this is why they're out of the scored batch entirely now.

**Removing the 7 real records did not change the qualitative result**:
precision and recall are still 1.0000 on the corrected, purely-synthetic
250-transaction batch (see Stage 2 below) - match rate shifted slightly
(90.80% vs. the old 91.83%) purely because the denominator shrank from 257 to
250 and the synthetic mismatch-injection RNG draws differ at that batch size,
not because anything about the matching logic changed.

## Stage 2: Reconciliation engine

Run: `python -m backend.reconciliation.run_reconciliation`
Validated against `backend/data/ground_truth.json` (250 transactions, 100%
synthetic, with deliberately injected rounding/timestamp-drift/missing/duplicate
mismatches across the synthetic ledger and bank statement).

| Metric | Value |
|---|---|
| Precision | 1.0000 |
| Recall | 1.0000 |
| Match rate (matches / total ground-truth txns) | 0.8520 (213/250) |
| True positives | 212 |
| of which resolved an *ambiguous* case | 5 |
| False positives | 0 |
| False negatives | 0 |
| Matches by tier | exact: 148, fuzzy: 45, **llm: 20** |
| Honest exceptions (unresolved rows) | 58 |
| Ground-truth verdicts | must_match: 207, no_counterpart: 29, ambiguous: 14 |

**These numbers changed when ambiguous mismatch kinds were added** (see
"Ambiguous cases and human review" below). The previous run - before those
kinds existed - was: match rate 0.9080 (227/250), tiers exact 176 / fuzzy 51
/ **llm 0**, 51 exceptions. Match rate fell because the dataset now genuinely
contains more unmatchable and undecidable rows, not because matching got
worse: precision and recall both still hit 1.0000, and the LLM tier went
from resolving **0** cases to **20**.

### Ambiguous cases and human review

Every exception in the earlier dataset was the same case - the counterpart
genuinely did not exist, because the only mismatch kind that produced an
exception was `missing`. That is a case with one obvious answer ("write it
off"), which gives a human reviewer nothing to actually adjudicate. Three
mismatch kinds were added to fix that:

| Kind | Weight | What it models | Verdict |
|---|---|---|---|
| `partial_settlement` | 3% | Only part of the payout released this cycle (rolling reserve / risk hold); amount short by 6–11% of net | `ambiguous` |
| `late_settlement_window` | 3% | Amount exact to the paisa, settlement date slipped 92–140h | `must_match` |
| `refund_not_debited` | 2% | Bank credited the payout before the refund was debited | `must_match` |

`duplicate` was also changed: it used to emit two byte-identical rows (so the
orphan was trivially identifiable and the fuzzy tier's scoring was never
exercised). The second copy now drifts 2–5% in amount and 30–180 minutes in
time, making "two similar credits against one ledger entry" a real question.

**Why the amount drift is a range, not a fixed percentage.** `fuzzy_match`'s
amount tolerance is `max(₹30, 8% of gross)`, and because amounts are
`uniform(150, 25_000)` the percentage term dominates for all but 2 of 250
rows. Measured, that makes the band a *cliff*: a flat 8.0% drift falls inside
tolerance for **250/250** rows, while 8.5% falls outside for **248/250**. A
single fixed percentage therefore yields an all-or-nothing population - which
is the very problem being fixed, just relabelled. `PARTIAL_SETTLEMENT_RANGE =
(0.89, 0.94)` straddles the boundary so some injections auto-match (proving
the engine still works) and the rest become genuine near-misses.

**`reconcile_verdict` - why recall stayed honest.** `should_fully_reconcile`
used to be a one-line structural test (`neither side is "missing"`), which
said nothing about whether the rows were *close enough* to pair. Any new kind
would have been silently counted as "must match" and then scored as a false
negative when the engine correctly escalated it. Ground truth now declares
intent per kind (`backend/ingestion/synthetic_data_generator.py::_verdict`):

- `must_match` - the counterpart exists and genuinely corresponds; failing to
  pair it is a real miss and costs recall.
- `ambiguous` - a counterpart exists but a human could decide either way.
  **Excluded from the recall denominator**, so the engine is neither rewarded
  for force-matching nor punished for escalating.
- `no_counterpart` - a side is genuinely absent; declining to match is correct.

One consequence worth recording: the LLM tier resolved 5 of the 14 ambiguous
transactions. Counting those in recall's numerator against a denominator that
excludes them produced a nonsensical **recall of 1.0242** on the first run -
a real bug, caught because the number was impossible. `validate.py` now
intersects the numerator with the denominator population and reports those 5
separately as `ambiguous_resolved` rather than letting them inflate the
headline.

**Human-in-the-loop review.** 26 of the 58 exceptions now carry at least one
candidate counterpart on the opposite side - i.e. a decision a person has to
make, rather than a foregone conclusion. `GET /api/reconciliation/review-queue`
serves each exception with its source row and candidates; `POST
/api/reconciliation/review` records a decision (`approved_match`,
`written_off`, `manually_paired`) with an optional note and reviewer into
`reconciliation_reviews`. That table is deliberately **not** part of any
`save_*` full-refresh cycle: every other derived table is rebuilt per
pipeline run, but a reviewer's decision records something a person actually
did, so re-running ingestion must not erase it (pinned by a test).

**Why match rate (85.2%) is below 100% while precision/recall are 100%:** the
shortfall has two genuinely different causes, which is why
`verdict_breakdown` reports them separately rather than as one number:

1. **29 transactions have no counterpart at all** (the injected `missing`
   kind) - there is no correct match to find, so leaving them unmatched is
   the correct behaviour, not a miss.
2. **14 are ambiguous** (`partial_settlement`) - a counterpart exists, but
   whether it should be paired is a judgment call. The engine resolved 5 via
   the LLM tier and escalated the remaining 9 to the review queue.

Plus the extra copies from injected duplicates, which legitimately have no
second counterpart. Precision/recall are computed only over pairs the engine
actually reported, against the must-match population, which is why they hit
1.0 exactly: every match it reported was correct, and every must-match pair
got found.

**Is this check circular?** No - confirmed by tracing the actual code path.
`validate_reconciliation` (`backend/reconciliation/validate.py`) builds its
`row_id -> txn_id` map from `ground_truth.json`, which is written by
`build_ground_truth` in `synthetic_data_generator.py` at generation time,
independently of any matching logic. The reconciliation engine
(`exact_match.py`, `fuzzy_match.py`, `llm_exception.py`) matches purely on
`order_id` (a legitimate shared join key, present on both the ledger and bank
export the same way a real merchant's systems would share it), amount
tolerance against the ledger's own recorded fee/GST/refund figures, and
timestamp proximity - it never reads the `row_id -> txn_id` mapping ground
truth uses to score it. Each row's `txn_id_hint` field is stored in Postgres
and passed through in `Transaction.raw`, but grepping `exact_match.py`,
`fuzzy_match.py`, and `llm_exception.py` confirms it is never referenced by
any matching code path - it really is invisible to the matcher, not just
documented as such. Precision/recall being exactly 1.0 is a real, non-circular
result on this synthetic dataset, not an artifact of the scoring method.

**LLM tier resolved 0 of the 250** - exact and fuzzy match, given the ledger's
own fee/GST/refund figures, handled the entire reconcilable set numerically.
This is intentional per the "minimize LLM calls" rule; the LLM tier exists for
harder real-world cases and is exercised here purely for the *exception
reasoning* on the 51 unresolved rows. The reason-label breakdown depends on
the LLM's live output for that run - check `/api/reconciliation/exceptions` or
the dashboard's Exception Ledger for the current run's actual split.

## Stage 3: Tax matcher - LLM fallback

Run: `python -m backend.tax_matcher.run_tax_matcher`

**Why the LLM fallback fired 0 times before this fix:** investigated by
reading the actual code paths, not assumed. `classify_by_rules`
(`backend/tax_matcher/rules.py`) only returns `None` (triggering the LLM
tier) when a required field (`had_refund`, `gst_on_fee_flag`, `fee_amount`) is
missing or malformed - that's a genuine, honest trigger, not an
over-confident rules engine silently guessing. The real cause was a **data
diversity gap**: `synthetic_data_generator.py` always populated all three
required fields for every transaction, so the rule tree - which exactly
mirrors the generator's own `true_tax_category` logic by design (documented
in both files as needed for honest scoring) - could resolve 100% of records
every time. The rules were never wrong; they were just never tested against
a genuinely ambiguous record because none existed in the generated data.

**Fix:** ~2% of synthetic transactions now carry `fee_amount_pending=True`
- the gateway hasn't computed/swept the fee yet, the same real-world state
`razorpay_adapter.py` already handles for live test-mode payments where
`settled_at`/`fee` come back `None`. `classify_by_rules` treats this as a
genuine data gap and declines to classify; `run_tax_matcher.py` also masks
`fee_amount`/`tax_on_fee` in the copy handed to the LLM fallback, so the LLM
is reasoning from what's genuinely available, not silently handed the answer.

| Metric | Value |
|---|---|
| Total transactions | 250 |
| Resolved by rules | 248 |
| Sent to LLM fallback | 2 |
| Unresolved (honest exceptions) | 0 |
| Accuracy vs. synthetic `true_tax_category` | 250/250 (1.0000) |

Both LLM-fallback cases were resolved correctly this run (both LLM tiers can
vary slightly run-to-run since the model is called live - check
`/api/tax/classifications` or the dashboard for the current run's actual
per-record reasoning).

## Stage 4: Forecaster

Run: `python -m backend.forecaster.train`

### Model A - `days_to_settle`

Plain scikit-learn `LinearRegression` (no polynomial curvature detected),
validated on a held-out split of the 250-transaction dataset (`n_train=200,
n_test=50`).

| Model | Target | MAE | MAPE |
|---|---|---|---|
| A | `days_to_settle` | 0.6667 days | 32.11% |

### Model B - split into `fee_deduction_pct` + `refund_deduction_pct`

**The original single Model B (MAE 0.0316, MAPE 126.83%) has been replaced.**
`deduction_pct` is bimodal - 0.95-correlated with `had_refund` (see
[`forecaster_diagnostics.md`](forecaster_diagnostics.md)) - and asking one
linear model to fit both the tight non-refund cluster (0.01–0.03) and the wide
refund cluster (0.68–0.99) with one coefficient set was the root cause of the
high MAPE. Per CLAUDE.md's originally-scoped optional refinement (now
required), Model B is split into two additive linear models:

- **`fee_deduction_pct`** = `(fee_amount + tax_on_fee) / txn_amount` - applies
  to every transaction, trained on all 250 rows. Features: `txn_amount`,
  `gst_on_fee_flag`, `payment_method` (`had_refund`/`refund_amount` dropped -
  causally irrelevant to the fee portion).
- **`refund_deduction_pct`** = `refund_amount / txn_amount` - trained *only*
  on `had_refund=1` rows (14 train / 3 test - a small subset, since only
  ~8% of transactions have a refund), so the ~92% of rows where this target
  is trivially zero don't dilute the fit. Features: `txn_amount`,
  `refund_amount`, `payment_method`.
- At inference, `total_deduction_pct = fee_deduction_pct + (refund_deduction_pct
  if had_refund else 0)` - see `backend/forecaster/predict.py`.

| Model | Target | n_train | n_test | MAE | MAPE |
|---|---|---|---|---|---|
| B (fee) | `fee_deduction_pct` | 200 | 50 | 0.0013 | 23.41% |
| B (refund) | `refund_deduction_pct` (had_refund=1 only) | 14 | 3 | 0.0519 | 13.85% |
| **B (combined)** | `total_deduction_pct` (fee + refund, gated) | - | 50 | **0.0037** | **20.13%** |

**Combined MAE dropped from 0.0316 to 0.0037 (8.5x lower); combined MAPE
dropped from 126.83% to 20.13% (6.3x lower)** - evaluated on the same overall
held-out test split (50 rows) as the original single model, so this is a
direct, apples-to-apples comparison. The split directly fixed the diagnosed
bimodality problem: the fee model no longer has to also represent the refund
cluster, and the refund model is no longer diluted by the ~92% zero rows.

**Caveat, reported honestly**: the refund submodel trains on only 14 rows and
tests on 3 - a small sample by construction (refunds are ~8% of transactions).
Its own MAE/MAPE (0.0519 / 13.85%) should be read with that in mind; more
refund transactions would tighten this considerably.

**See [`forecaster_diagnostics.md`](forecaster_diagnostics.md)** for updated
learning curves, predicted-vs-actual, and residual plots for all three models
(A, B-fee, B-refund).

## Stage 5: Operational forecasting (GMV / refund / settlement) & cash position

Run: `python -m backend.forecaster.train` (GMV) - refund/settlement are
deterministic baselines, nothing to train.

Model A/B (above) predict **per-transaction** `days_to_settle` and
`deduction_pct`. This stage covers three separate **daily-aggregate**
operational forecasts, explored in
[`ML/notebooks/daily_gmv_refund_settlement_experiments.ipynb`](../ML/notebooks/daily_gmv_refund_settlement_experiments.ipynb)
against the 2,250-row expanded CSV, then productionized (or deliberately
rejected) against the live 250-row Postgres dataset:

| Forecast | Method validated | Notebook result (2,250-row CSV) | Production decision |
|---|---|---|---|
| **GMV** (next-day total GMV) | Linear Regression vs. naive previous-day | MAE ≈ ₹87,993.95 vs. naive ≈ ₹115,860.80 (≈24% better) | **Deployed** - `backend/forecaster/gmv.py`, same `shift(1)`-then-`rolling()` feature recipe, trained from Postgres. Chronological (not random) 80/20 split - see "Data leakage" note below. |
| **Refund** (next-day total refunds) | Linear Regression vs. naive previous-day | LR MAE ≈ ₹12,536.87 vs. naive MAE ≈ ₹8,578.12 - **46.15% worse** | **Rejected.** Production uses the naive baseline directly: `expected_refunds_tomorrow = total_refunds_today` (`backend/forecaster/refund_baseline.py`). |
| **Settlement** (next-day net settlement) | Linear Regression vs. naive previous-day | LR MAE ≈ ₹144,930.50 vs. naive MAE ≈ ₹93,583.45 - **54.87% worse** | **Rejected.** Production uses the naive baseline directly: `expected_settlement_tomorrow = total_settlement_today` (`backend/forecaster/settlement_baseline.py`), structured so it can later be replaced by a per-transaction pipeline forecast (created_at + Model A's predicted days_to_settle + amount/fees/refunds/tax) without changing the cash engine's interface. |

**On the live 250-row Postgres dataset** (a much smaller sample than the
2,250-row exploratory CSV, so the numbers below are directionally consistent
but not identical in magnitude), the GMV model trained via
`python -m backend.forecaster.train` reports (see
`/api/forecaster/metrics`'s `gmv` key for the current run's exact numbers):
`n_train`/`n_test` split from ~92 days of daily aggregates, MAE and naive-MAE
both computed the same way as the notebook. The refund and settlement
baselines are not retrained - they're pure arithmetic, re-evaluated fresh
against whatever "today" is in the current dataset every time they're called.

**Every forecast response carries its own method**, so the API/dashboard
never implies an ML forecast where the real method is a baseline:
```json
{"value": 6929.97, "method": "naive_previous_day", "model": null}
{"value": 123456.78, "method": "linear_regression", "model": "gmv"}
```

**Data leakage**: all three daily-aggregate models compute lag/rolling
features with `.shift(1)` applied *before* `.rolling(...)`, so a feature for
day T never includes day T's own (or any later day's) total - verified by a
unit test (`backend/tests/test_gmv_forecaster.py`). Evaluation uses a
chronological split (`X[:split]`/`X[split:]` on date-sorted rows), never
`sklearn.model_selection.train_test_split`'s random shuffle, since shuffling
a time series would let the model train on days after the ones it's tested
on.

### Cash-position engine

`backend/finance/cash_position.py` computes, deterministically (no LLM):

```text
expected_net_cash_flow = expected_settlement - expected_refunds
projected_cash          = current_cash + expected_net_cash_flow
```

- **`current_cash`** has no authoritative source in this synthetic dataset -
  it is never fabricated. `GET /api/cash-position` accepts it as a
  `current_cash` query parameter (defaulted to ₹10,00,000 for a convenient
  demo call, not presented as a real balance).
- **`expected_settlement`** = the settlement baseline above.
- **`expected_refunds`** = the refund baseline above.

Exposed via `GET /api/cash-position` and, for forward-looking cash-position
questions, through the Q&A agent's retrieval context (`backend/qa_agent/retriever.py`) -
the LLM only narrates the number `compute_cash_position` already produced, it
never recomputes it.
