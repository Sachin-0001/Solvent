# ML

Exploratory/educational notebooks for Solvent's Stage 4 forecaster models, plus
the flat CSV they train on. **This is not where the models are canonically
trained** — that's `python -m backend.forecaster.train` from the repo root,
which reads live from Postgres and persists both the `.joblib` artifacts
(`backend/forecaster/models/`) and the validation metrics
(`docs/metrics.md`) that the API and dashboard actually serve.

This folder exists so the exact same training run — same algorithm, same
feature set, same `random_state`/`test_size` — can be opened, read, and
re-executed cell by cell in Jupyter, independent of a running Postgres
instance.

```
ML/
  data/
    base_transactions.csv       # base_transactions export, expanded with extra synthetic rows (see below)
  notebooks/
    model_a_days_to_settle_training.ipynb   # Model A: predicts settlement lag
    model_b_deduction_pct_training.ipynb    # Model B: predicts deduction fraction
    artifacts/                  # notebook's own .joblib output (gitignored, not the canonical one)
```

## `base_transactions.csv` — data volume

The first **257 rows** (7 `razorpay_real` + 250 `synthetic`) are the exact
pipeline export the two notebooks were originally validated against, and are
what `docs/metrics.md` and `docs/forecaster_diagnostics.md` report numbers
for.

The remaining **2,000 rows** (all `source=synthetic`, `txn_id` continuing
from `TXN00258`) were generated afterward, on request, for anyone who wants
more volume to train on — **not scraped or fabricated ad hoc**: they're
produced by calling the project's own
`backend.ingestion.synthetic_data_generator.generate_base_transactions()`
with a different seed (`20260831` vs. the original ingestion run's `42`) and
the same `start_date`/`end_date` window, so they follow the identical
generative model as the original 250 synthetic rows — same payment-method
mix, same fee-percent-by-method table, same weekend/holiday/dispute
settlement-lag logic, same `deduction_pct` construction from
fee+GST+refund. Spot-checked against the original 257: payment-method
shares, `txn_amount` range, `days_to_settle` distribution, refund/dispute
rates, and the `corr(deduction_pct, had_refund) ≈ 0.95` relationship all
hold within noise across the full 2,257 rows. No `txn_id` collisions with
the original rows; the only duplicate `order_id`s in the file are two
pre-existing real Razorpay orders with multiple payment attempts (rows 1-5),
not anything introduced by the added rows.

**This means re-running the notebooks against the current (2,257-row) CSV
will *not* reproduce `docs/metrics.md`'s exact numbers** — that's expected;
those numbers were validated on the original 257-row pipeline output. New
numbers from the larger dataset are a legitimate, separate result, not a
discrepancy to chase.

## Running

```bash
source .venv/bin/activate       # repo-root venv; needs pandas, scikit-learn, matplotlib, joblib
pip install jupyter ipykernel   # only needed to open/execute the notebooks interactively
jupyter notebook ML/notebooks/
```

Both notebooks are committed **already executed against the original
257-row file** — the printed metrics/plots baked into them right now are
the 257-row numbers that match `docs/metrics.md` exactly. Re-running either
notebook's cells top to bottom will re-fit against whatever is currently in
`ML/data/base_transactions.csv` — i.e. all 2,257 rows, once the additional
synthetic rows described above are present — and produce new numbers from
the larger set.

To go back to a from-scratch, Postgres-sourced 257-row export instead of
the checked-in CSV (e.g. after re-running the pipeline with different
synthetic data):

```bash
python -c "
import pandas as pd
from backend import db
rows = db.load_base_transactions()
cols = ['txn_id','source','razorpay_payment_id','order_id','txn_amount','payment_method',
        'created_at','day_of_week','is_weekend_or_holiday','merchant_category',
        'had_dispute_flag','had_refund','refund_amount','gst_on_fee_flag','fee_amount',
        'tax_on_fee','fee_pct','days_to_settle','deduction_pct','settled_at','status',
        'true_tax_category']
pd.DataFrame(rows)[cols].to_csv('ML/data/base_transactions.csv', index=False)
"
```

Row order matters if you want a fresh export to reproduce
`docs/metrics.md`'s exact numbers: `train_test_split`'s row-to-split
assignment depends on input row order for a fixed `random_state`, and the
command above preserves Postgres's default read order (not sorted by
`txn_id`) for exactly that reason.

See [`../docs/metrics.md`](../docs/metrics.md) and
[`../docs/forecaster_diagnostics.md`](../docs/forecaster_diagnostics.md) for
the production-run numbers and the fuller root-cause writeup these notebooks
reproduce inline.
