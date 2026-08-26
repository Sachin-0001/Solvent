"""
Step 3 entry point. Run with: python -m backend.tax_matcher.run_tax_matcher

Classifies every base transaction for GST treatment, then compares against the
synthetic true_tax_category label purely for transparency (this isn't a hard
gate like reconciliation/forecaster, but honest numbers matter here too).
"""

from __future__ import annotations

from backend import db
from backend.tax_matcher.matcher import classifications_to_dicts, run_tax_matcher


def main() -> None:
    transactions = db.load_base_transactions()

    result = run_tax_matcher(transactions)
    classifications = classifications_to_dicts(result["classifications"])

    print("=== Tax matcher run ===")
    print(f"Total transactions: {len(transactions)}")
    print(f"Resolved by rules: {result['rule_count']}")
    print(f"Sent to LLM fallback: {result['llm_count']}")
    print(f"Unresolved (honest exceptions): {result['exception_count']}")

    truth = {t["txn_id"]: t["true_tax_category"] for t in transactions}
    correct = sum(1 for c in classifications if truth.get(c["txn_id"]) == c["category"])
    total = len(classifications)
    print(f"\nAccuracy vs synthetic true_tax_category: {correct}/{total} ({correct/total:.4f})")

    from collections import Counter

    category_counts = Counter(c["category"] for c in classifications)
    print(f"Category distribution: {dict(category_counts)}")

    if result["exception_count"]:
        print("\nExceptions:")
        for c in result["classifications"]:
            if c.category == "unresolved":
                print(f"  {c.txn_id}: {c.reasoning}")

    db.save_tax_classifications(classifications)
    print("\nWrote (Postgres): tax_classifications")


if __name__ == "__main__":
    main()
