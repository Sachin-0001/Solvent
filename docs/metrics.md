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
harder real-world cases (see note below) and is exercised here purely for the
*exception reasoning* on the 54 unresolved rows (50 correctly labeled
"missing_counterpart", 3 "likely_duplicate", 1 "unexplained" — see
conversation for the one minor inconsistent label between two symmetric
duplicate rows).

## Stage 4: Forecaster

_Not yet run — will be filled in after Model A / Model B validation._
