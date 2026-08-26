"""
Step 1 entry point. Run with:  python -m backend.ingestion.run_ingestion

1. Pulls whatever real transactions exist on the Razorpay test account
   (Orders -> Payments -> Settlements) via RazorpayAdapter. Test accounts often
   have zero or very few, and that's fine — it's supplemented below.
2. Generates a synthetic base-transaction truth set (padded to a usable volume)
   plus a synthetic internal ledger and bank statement, each with deliberately
   injected mismatches.
3. Augments ledger/bank rows with realistic narration text via Groq (one shared
   wrapper, batched calls).
4. Writes raw/processed files and ground_truth.json, then prints a summary.
"""

from __future__ import annotations

import json

from backend import db
from backend.config import RAW_DATA_DIR
from backend.ingestion.groq_augment import augment_rows
from backend.ingestion.razorpay_adapter import RazorpayAdapter
from backend.ingestion.synthetic_data_generator import (
    build_ground_truth,
    generate_base_transactions,
    generate_bank_statement,
    generate_internal_ledger,
)

N_SYNTHETIC_BASE = 250


def fetch_real_transactions() -> list[dict]:
    try:
        adapter = RazorpayAdapter()
        txns = adapter.fetch(order_count=100)
        print(f"[razorpay] fetched {len(txns)} real payment(s) from test-mode account")
        return [
            {
                "source_id": t.source_id,
                "order_id": t.order_id,
                "amount": t.amount,
                "method": t.method,
                "created_at": t.created_at,
            }
            for t in txns
            if t.created_at
        ]
    except Exception as e:
        print(f"[razorpay] skipped live fetch ({e.__class__.__name__}: {e})")
        return []


def main() -> None:
    real_transactions = fetch_real_transactions()

    base_transactions = generate_base_transactions(
        n_synthetic=N_SYNTHETIC_BASE, real_transactions=real_transactions
    )

    ledger_rows, ledger_mismatch_map = generate_internal_ledger(base_transactions)
    bank_rows, bank_mismatch_map = generate_bank_statement(base_transactions)

    print(f"[synthetic] {len(base_transactions)} base transactions "
          f"({len(real_transactions)} real + {N_SYNTHETIC_BASE} synthetic)")
    print(f"[synthetic] {len(ledger_rows)} ledger rows, {len(bank_rows)} bank rows generated")

    print("[groq] augmenting ledger rows with narration text...")
    ledger_rows = augment_rows(ledger_rows, kind="ledger")
    print("[groq] augmenting bank rows with narration text...")
    bank_rows = augment_rows(bank_rows, kind="bank")

    ground_truth = build_ground_truth(base_transactions, ledger_mismatch_map, bank_mismatch_map)

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Raw ledger/bank files stay as files — they stand in for the external
    # documents (CSV/JSON exports) a real merchant's systems would hand us.
    # Everything ingestion derives from them becomes the canonical, indexed,
    # queryable state in Postgres — what every downstream stage reads from.
    (RAW_DATA_DIR / "internal_ledger.json").write_text(json.dumps(ledger_rows, indent=2))
    (RAW_DATA_DIR / "bank_statement.json").write_text(json.dumps(bank_rows, indent=2))

    db.init_db()
    db.save_base_transactions(base_transactions)
    db.save_ledger_rows(ledger_rows)
    db.save_bank_rows(bank_rows)
    db.save_ground_truth(ground_truth)

    mismatch_counts: dict[str, int] = {}
    for g in ground_truth:
        key = f"ledger={g['ledger_mismatch']},bank={g['bank_mismatch']}"
        mismatch_counts[key] = mismatch_counts.get(key, 0) + 1

    print("\n=== Ingestion summary ===")
    print(f"Base transactions: {len(base_transactions)}")
    print(f"Ledger rows: {len(ledger_rows)}  Bank rows: {len(bank_rows)}")
    print(f"Ground truth entries: {len(ground_truth)}")
    fully_reconcilable = sum(1 for g in ground_truth if g["should_fully_reconcile"])
    print(f"Should fully reconcile (both sides present): {fully_reconcilable}/{len(ground_truth)}")
    print("Mismatch combinations:")
    for key, count in sorted(mismatch_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {key}: {count}")
    print(f"\nWrote (raw files): {RAW_DATA_DIR/'internal_ledger.json'}, {RAW_DATA_DIR/'bank_statement.json'}")
    print("Wrote (Postgres): base_transactions, ledger_rows, bank_rows, ground_truth")


if __name__ == "__main__":
    main()
