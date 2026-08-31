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
    base_transactions.csv       # flat export of the base_transactions table (257 rows)
  notebooks/
    model_a_days_to_settle_training.ipynb   # Model A: predicts settlement lag
    model_b_deduction_pct_training.ipynb    # Model B: predicts deduction fraction
    artifacts/                  # notebook's own .joblib output (gitignored, not the canonical one)
```

## Running

```bash
source .venv/bin/activate       # repo-root venv; needs pandas, scikit-learn, matplotlib, joblib
pip install jupyter ipykernel   # only needed to open/execute the notebooks interactively
jupyter notebook ML/notebooks/
```

Both notebooks are already executed in place — opening one in GitHub or
Jupyter shows real output (printed metrics, plots) from the last run, not
empty cells. Re-run them any time after regenerating
`ML/data/base_transactions.csv` from a fresh pipeline run:

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

The row order in that CSV matters: it preserves Postgres's default read
order (not sorted by `txn_id`), because `train_test_split`'s row-to-split
assignment depends on input order for a fixed `random_state`. With that
order preserved, both notebooks reproduce `docs/metrics.md`'s numbers
exactly (Model A: MAE 0.5951 / MAPE 30.3%; Model B: MAE 0.0316 / MAPE
126.83%) rather than just approximately.

See [`../docs/metrics.md`](../docs/metrics.md) and
[`../docs/forecaster_diagnostics.md`](../docs/forecaster_diagnostics.md) for
the production-run numbers and the fuller root-cause writeup these notebooks
reproduce inline.
