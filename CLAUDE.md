# Solvent — AI Finance-Controller Pipeline

Built for the Razorpay AI Buildathon (Track 04).

## Concept

Solvent reconciles a merchant's transactions across three sources (a real Razorpay
test-mode settlement feed, a synthetic internal ledger, a synthetic bank statement),
classifies each reconciled line for GST treatment, forecasts future settlement timing
and deduction amounts using two trained regression models, and answers merchant
questions about their settlements via an LLM-backed Q&A agent — all surfaced through
a Next.js dashboard.

## Architecture — strict dependency order

Each stage depends on the previous one's validated output. Do not parallelize across
stages. Stages 2 and 4 require reporting real validation numbers before proceeding.

### 1. Data ingestion (`backend/ingestion/`)
- Single ingestion **adapter interface** (`base.py`) with swappable implementations:
  - `razorpay_adapter.py` — real Razorpay test-mode API via the `razorpay` Python SDK.
    Flow: Orders → Payments → Settlements.
  - `synthetic_adapter.py` — reads generated synthetic internal ledger + bank statement.
  - `pdf_adapter.py` — **documented stretch, not built.** Future adapter for real bank
    PDF statements. Left as a stub + doc note so the interface is proven pluggable.
- `synthetic_data_generator.py` — builds internal ledger + bank statement with
  deliberately injected mismatches: rounding differences, timestamp drift,
  missing entries, duplicate entries.
- `groq_augment.py` — one LLM call (via the shared Groq wrapper) to add realistic
  text fields (narrations, descriptions) on top of synthetic rows.
- Saves `ground_truth.json` recording the injected correct mappings, used later to
  score the reconciliation engine honestly.

### 2. Reconciliation engine (`backend/reconciliation/`)
Order of resolution per transaction:
1. Exact match (pure code)
2. Fuzzy match with tolerance bands (fee %, settlement lag) (pure code)
3. LLM exception reasoning (Groq) — **only** for the unmatched residual after 1+2
- Validated against `ground_truth.json`: match rate, precision, recall reported honestly.
- **Gate:** do not proceed to step 3 (tax matcher) until these numbers are computed
  and reported to the user.

### 3. Tax-line matcher (`backend/tax_matcher/`)
- Rule-based classifier first (taxable sale, GST-on-fee, exempt, refund/credit-note
  adjustment) — pure code, handles the clear-cut majority.
- LLM fallback (Groq) only for line items the rules can't resolve.
- **Not a trained ML classifier.** No Random Forest, XGBoost, or similar here.

### 4. Forecaster (`backend/forecaster/`)
Two separate trained regression models — both run for every transaction, no router:
- **Model A** — predicts `days_to_settle` from: txn_amount, payment_method (one-hot),
  day_of_week, is_weekend_or_holiday, merchant_category, had_dispute_flag.
- **Model B** — predicts `deduction_pct` from: txn_amount, payment_method (one-hot),
  had_refund, refund_amount, gst_on_fee_flag.
- Baseline: scikit-learn linear regression. Only try polynomial features on
  txn_amount if residuals show clear curvature; report whichever validates better.
- **No LLM, no LSTM/RNN, no neural net, no SVM.** Pure supervised regression on
  tabular features.
- **Gate:** validate both against held-out data, report MAE/MAPE to the user before
  proceeding to step 5.

### 5. Settlement Q&A agent (`backend/qa_agent/`)
- Retrieves relevant reconciled + tax-classified records (and forecaster output for
  forward-looking questions).
- Passes retrieved context to Groq to generate a plain-language answer citing
  specific figures.

### 6. Next.js frontend (`frontend/`)
- Reconciliation view: live match rate + exception list with reasoning shown.
- Q&A chat interface.
- 7-day cash forecast chart with a confidence band.

## Technical rules (enforced throughout)

- **Single Groq entry point.** All Groq calls go through one shared wrapper
  (`backend/llm/groq_client.py`) with JSON extraction/repair built in. Never call the
  Groq SDK directly from individual modules.
- **Minimize LLM calls by design.** Exact/fuzzy matching, the tax rules engine, and
  both forecaster models are pure code/ML with zero LLM calls. LLM calls only happen
  for: reconciliation's exception residual, tax matcher's fallback, and the Q&A agent.
- **Honest exceptions.** Every batch operation (reconciliation, tax matching) must
  produce a reasoned exception list for what it couldn't resolve. Never suppress or
  hide unresolved cases to make numbers look cleaner.
- **Pluggable ingestion.** Adapter interface must support the synthetic file reader,
  the DB-backed reader, the live Razorpay API reader, and leave a documented (not
  built) slot for a future PDF-statement adapter.
- No hardcoded or placeholder API keys anywhere in the repo. Keys come from `.env`
  (see `.env.example`), which is gitignored.

## Storage layer

Postgres (`backend/db.py`) is the canonical store for everything ingestion derives
and every downstream stage reads — replacing the flat-JSON-files-in-memory approach
the pipeline started with, which doesn't hold up past a few hundred rows (no
indexing, full read/write of the whole dataset every run, no concurrent access).

- Raw `internal_ledger.json` / `bank_statement.json` stay as **files** — they stand
  in for the external documents (CSV/JSON exports) a real merchant's systems would
  hand over. Ingestion parses them the same way it always did.
- Everything ingestion *derives* — `base_transactions`, `ledger_rows`, `bank_rows`,
  `ground_truth`, `reconciliation_matches`/`reconciliation_exceptions`,
  `tax_classifications`, `forecaster_metrics`, `record_embeddings` — is a Postgres
  table with indexes on `order_id`/`txn_id`/`created_at`, populated via full-refresh
  (TRUNCATE + bulk insert) per run. See `backend/db.py`'s module docstring for why
  full-refresh matches this pipeline's semantics and where it'd need to change for
  a live, ever-growing transaction stream instead of a regenerated synthetic world.
- `backend/ingestion/db_adapter.py` provides `DBLedgerAdapter`/`DBBankAdapter` —
  the same `IngestionAdapter` interface as the file-based ones, sourcing from the
  indexed tables instead of re-parsing a file on every call. Reconciliation uses
  these; this is the adapter pattern actually earning its keep (downstream code is
  unchanged when the source implementation swaps).

## Q&A retrieval

`backend/qa_agent/embeddings.py` does real semantic retrieval — a local embedding
model (`sentence-transformers/all-MiniLM-L6-v2`, no API key, runs offline), not
keyword matching. Embeddings are computed once per record and persisted in
`record_embeddings`; a merchant question is embedded and compared via brute-force
cosine similarity in numpy. This is not a "small dataset" simplification: keyword
matching is fragile at *any* scale (a real question phrased outside the guessed
keyword list gets zero context regardless of data volume) — semantic retrieval is
just the correct approach. Brute-force cosine search is fine at this dataset's
size; `record_embeddings`'s docstring in `db.py` notes the pgvector-ANN-index
upgrade path for when volume actually warrants it (not installed on this instance).
An explicit order/txn ID mention in the question still short-circuits straight to
that record — strictly better than a similarity search when the merchant already
named exactly what they're asking about.

## Repo layout

```
Solvent/
  backend/
    ingestion/        # adapters, synthetic generator, ground_truth.json
    reconciliation/    # exact/fuzzy match, LLM exception reasoning, validation
    tax_matcher/        # rule engine + LLM fallback
    forecaster/         # Model A (days_to_settle), Model B (deduction_pct)
    qa_agent/            # retrieval + Groq-backed Q&A
    llm/                 # single shared Groq wrapper
    data/                # raw/processed data, ground_truth.json
    tests/
  frontend/            # Next.js dashboard
  docs/                # metrics.md, architecture notes
  CLAUDE.md
  .env.example
```

## Status

Build proceeds stage by stage per the dependency order above. See conversation /
commit history for current stage. Validation numbers for reconciliation (stage 2)
and forecaster (stage 4) are reported to the user before advancing — check
`docs/metrics.md` for the latest recorded numbers.
