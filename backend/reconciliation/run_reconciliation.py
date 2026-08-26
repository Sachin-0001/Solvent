"""
Step 2 entry point. Run with: python -m backend.reconciliation.run_reconciliation

Runs exact -> fuzzy -> LLM exception matching over the ingested ledger/bank data,
validates the result against ground_truth.json, and prints match rate, precision,
recall, plus the honest exception list breakdown. This is the gate the project
brief requires before moving on to the tax matcher.
"""

from __future__ import annotations

from backend import db
from backend.reconciliation.engine import exceptions_to_dicts, matches_to_dicts, run_reconciliation
from backend.reconciliation.validate import validate_reconciliation


def main() -> None:
    result = run_reconciliation()
    matches = matches_to_dicts(result["matches"])
    exceptions = exceptions_to_dicts(result["exceptions"])

    print("=== Reconciliation run ===")
    print(f"Ledger rows: {result['total_ledger_rows']}  Bank rows: {result['total_bank_rows']}")
    print(f"Tier counts: {result['tier_counts']}")
    print(f"Total matches: {len(matches)}  Total exceptions: {len(exceptions)}")

    metrics = validate_reconciliation(matches, exceptions)

    print("\n=== Validation against ground_truth.json ===")
    print(f"Ground truth transactions: {metrics['total_ground_truth_txns']}")
    print(f"Should fully reconcile: {metrics['should_fully_reconcile']}")
    print(f"Reported matches: {metrics['reported_matches']}")
    print(f"True positives: {metrics['true_positives']}")
    print(f"False positives: {metrics['false_positives']}")
    print(f"False negatives: {metrics['false_negatives']}")
    print(f"PRECISION: {metrics['precision']:.4f}")
    print(f"RECALL: {metrics['recall']:.4f}")
    print(f"MATCH RATE: {metrics['match_rate']:.4f}")
    print(f"Tier breakdown of matches: {metrics['tier_breakdown']}")
    print(f"Exception count: {metrics['exception_count']}")
    if metrics["unresolved_should_reconcile_txn_ids"]:
        print(
            f"Unresolved txns that SHOULD have reconciled "
            f"({len(metrics['unresolved_should_reconcile_txn_ids'])}): "
            f"{metrics['unresolved_should_reconcile_txn_ids'][:15]}"
            f"{'...' if len(metrics['unresolved_should_reconcile_txn_ids']) > 15 else ''}"
        )

    db.save_reconciliation_matches(matches)
    db.save_reconciliation_exceptions(exceptions)
    print("\nWrote (Postgres): reconciliation_matches, reconciliation_exceptions")


if __name__ == "__main__":
    main()
