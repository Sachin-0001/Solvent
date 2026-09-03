"""
Scores the reconciliation engine's output against ground_truth.json. This is the
only place allowed to know which row_id belongs to which underlying transaction —
the engine itself never sees that mapping, so these numbers are an honest test of
the matching logic, not a self-report.
"""

from __future__ import annotations

from backend import db


def _row_to_txn_map(ground_truth: list[dict]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for g in ground_truth:
        for row_id in g["ledger_row_ids"]:
            mapping[row_id] = g["txn_id"]
        for row_id in g["bank_row_ids"]:
            mapping[row_id] = g["txn_id"]
    return mapping


def validate_reconciliation(matches: list[dict], exceptions: list[dict]) -> dict:
    ground_truth = db.load_ground_truth()
    row_to_txn = _row_to_txn_map(ground_truth)
    should_reconcile_txn_ids = {g["txn_id"] for g in ground_truth if g["should_fully_reconcile"]}

    true_positive_txn_ids: set[str] = set()
    false_positives = 0

    for m in matches:
        l_txn = row_to_txn.get(m["ledger_row_id"])
        b_txn = row_to_txn.get(m["bank_row_id"])
        if l_txn is not None and l_txn == b_txn:
            true_positive_txn_ids.add(l_txn)
        else:
            false_positives += 1

    true_positives = len(true_positive_txn_ids)
    false_negatives = len(should_reconcile_txn_ids - true_positive_txn_ids)

    # Recall must be measured over the *same* population as its denominator.
    # Ambiguous transactions are deliberately excluded from
    # should_fully_reconcile (a human decides them, so the engine is neither
    # rewarded for force-matching nor penalized for escalating) — but the
    # engine sometimes resolves one anyway via the LLM tier. Counting those
    # in the numerator against a denominator that excludes them produced a
    # nonsensical recall > 1.0, so they're intersected out here and reported
    # separately as `ambiguous_resolved` instead.
    recall_true_positives = len(true_positive_txn_ids & should_reconcile_txn_ids)
    ambiguous_resolved = true_positives - recall_true_positives

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else 0.0
    recall = (
        recall_true_positives / len(should_reconcile_txn_ids) if should_reconcile_txn_ids else 0.0
    )

    total_txns = len(ground_truth)
    match_rate = len(matches) / total_txns if total_txns else 0.0

    tier_breakdown: dict[str, int] = {}
    for m in matches:
        tier_breakdown[m["tier"]] = tier_breakdown.get(m["tier"], 0) + 1

    # The match-rate shortfall has two genuinely different causes, and
    # reporting one number for both is misleading: "no counterpart exists"
    # (nothing to find) vs "a counterpart exists but the call is ambiguous"
    # (a human decides). Broken out so docs/metrics.md can attribute it
    # honestly. Older ground-truth rows predate this field, hence the default.
    verdict_breakdown: dict[str, int] = {}
    for g in ground_truth:
        verdict = g.get("reconcile_verdict") or "must_match"
        verdict_breakdown[verdict] = verdict_breakdown.get(verdict, 0) + 1

    return {
        "total_ground_truth_txns": total_txns,
        "should_fully_reconcile": len(should_reconcile_txn_ids),
        "reported_matches": len(matches),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        # Correct pairings the engine found on transactions ground truth
        # labelled ambiguous — real wins, but outside recall's denominator,
        # so surfaced on their own rather than inflating the headline.
        "ambiguous_resolved": ambiguous_resolved,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "match_rate": round(match_rate, 4),
        "tier_breakdown": tier_breakdown,
        "verdict_breakdown": verdict_breakdown,
        "exception_count": len(exceptions),
        "unresolved_should_reconcile_txn_ids": sorted(should_reconcile_txn_ids - true_positive_txn_ids),
    }
