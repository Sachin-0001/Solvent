"""
Tier 3: LLM exception reasoning. The only tier that calls Groq, and only for
whatever exact + fuzzy match left unresolved — never the whole dataset.

Two situations reach here:
1. A candidate exists on both sides for the same order_id, but the numeric gap
   was too large for fuzzy match's tolerance band (the common case: a refund
   that isn't visible in the raw amount fields, only in the ledger's status).
   The LLM is given both records and decides whether they genuinely correspond.
2. No candidate exists on the other side at all (a true "missing" injection, or
   the leftover half of a duplicate whose twin was already claimed by fuzzy
   match). The LLM produces a plain-language explanation for the exception
   list — it is not asked to invent a match that doesn't exist.

Every row that reaches this tier ends up either in `matches` (LLM-resolved,
with an explanation) or in `exceptions` (unresolved, with an honest reason) —
nothing is silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.ingestion.base import Transaction
from backend.llm.groq_client import GroqError, call_groq_json
from backend.reconciliation.exact_match import (
    MatchResult,
    _group_by_order_id,
    _hours_between,
    expected_net,
)

BATCH_SIZE = 12

SYSTEM_PROMPT = (
    "You are a reconciliation analyst for an Indian payment-aggregator merchant. "
    "You are given ledger and bank-statement records that automated exact/fuzzy "
    "matching could not confidently pair. Decide, for each item, whether the "
    "candidate pair genuinely corresponds to the same underlying transaction "
    "(e.g. the gap is explained by a refund or credit-note deduction visible in "
    "the ledger status) or whether it should stay unresolved. Be conservative: "
    "only declare a match when the explanation is concrete and specific."
)


@dataclass
class ExceptionResult:
    row_id: str
    side: str  # "ledger" | "bank"
    order_id: str | None
    reason: str
    explanation: str


def _txn_summary(t: Transaction) -> dict[str, Any]:
    return {
        "row_id": t.source_id,
        "order_id": t.order_id,
        "amount": t.amount,
        "method": t.method,
        "status": t.status,
        "fee": t.fee,
        "tax_on_fee": t.raw.get("tax_on_fee"),
        "refund_amount": t.raw.get("refund_amount"),
        "timestamp": t.created_at,
    }


def _call_llm_batch(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    prompt = (
        "For each item, decide a resolution. Items:\n"
        f"{items}\n\n"
        "Respond with a JSON object mapping row_id -> "
        '{"resolution": "matched"|"missing_counterpart"|"likely_duplicate"|"unexplained", '
        '"matched_row_id": string or null, "explanation": short string}.\n'
        '"matched" is only valid when a "candidate" field was provided for that '
        "item and you are confident it corresponds — in that case matched_row_id "
        "must equal the candidate's row_id."
    )
    try:
        result = call_groq_json(prompt, system=SYSTEM_PROMPT, max_tokens=3000)
        if isinstance(result, dict):
            return result
    except (ValueError, GroqError):
        pass
    return {}


def llm_exception_pass(
    remaining_ledger: list[Transaction], remaining_bank: list[Transaction]
) -> tuple[list[MatchResult], list[ExceptionResult]]:
    ledger_by_order = _group_by_order_id(remaining_ledger)
    bank_by_order = _group_by_order_id(remaining_bank)
    all_order_ids = set(ledger_by_order) | set(bank_by_order)

    items: list[dict[str, Any]] = []
    lookup: dict[str, tuple[str, Transaction, Transaction | None]] = {}  # row_id -> (side, txn, candidate)

    for order_id in all_order_ids:
        lg = list(ledger_by_order.get(order_id, []))
        bg = list(bank_by_order.get(order_id, []))

        # Greedily pair the closest-amount candidates across both sides so every
        # row is accounted for exactly once, however many rows sit on each side
        # (duplicate injection can leave 2-vs-1 or 1-vs-2 groups here).
        pairs: list[tuple[Transaction, Transaction]] = []
        while lg and bg:
            best = None
            for i, l in enumerate(lg):
                net = expected_net(l)
                for j, b in enumerate(bg):
                    diff = abs(b.amount - net)
                    if best is None or diff < best[0]:
                        best = (diff, i, j)
            _, i, j = best
            pairs.append((lg.pop(i), bg.pop(j)))

        for l, b in pairs:
            items.append(
                {
                    "row_id": l.source_id,
                    "side": "ledger",
                    "record": _txn_summary(l),
                    "candidate": _txn_summary(b),
                }
            )
            lookup[l.source_id] = ("ledger", l, b)

        for l in lg:  # leftover ledger rows with no remaining bank candidate
            items.append({"row_id": l.source_id, "side": "ledger", "record": _txn_summary(l)})
            lookup[l.source_id] = ("ledger", l, None)
        for b in bg:  # leftover bank rows with no remaining ledger candidate
            items.append({"row_id": b.source_id, "side": "bank", "record": _txn_summary(b)})
            lookup[b.source_id] = ("bank", b, None)

    resolutions: dict[str, dict[str, Any]] = {}
    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start : start + BATCH_SIZE]
        resolutions.update(_call_llm_batch(batch))

    matches: list[MatchResult] = []
    exceptions: list[ExceptionResult] = []
    already_matched: set[str] = set()

    for row_id, (side, txn, candidate) in lookup.items():
        if row_id in already_matched:
            continue
        res = resolutions.get(row_id)
        if res and res.get("resolution") == "matched" and candidate is not None:
            matched_id = res.get("matched_row_id")
            if matched_id == candidate.source_id:
                time_diff = _hours_between(candidate.created_at, txn.created_at)
                ledger_txn, bank_txn = (txn, candidate) if side == "ledger" else (candidate, txn)
                matches.append(
                    MatchResult(
                        ledger_txn.source_id,
                        bank_txn.source_id,
                        txn.order_id,
                        "llm",
                        abs(bank_txn.amount - expected_net(ledger_txn)),
                        time_diff,
                        explanation=res.get("explanation"),
                    )
                )
                already_matched.add(txn.source_id)
                already_matched.add(candidate.source_id)
                continue

        reason = (res or {}).get("resolution", "unexplained")
        explanation = (res or {}).get(
            "explanation",
            "No confident resolution from automated matching or LLM reasoning.",
        )
        exceptions.append(ExceptionResult(row_id, side, txn.order_id, reason, explanation))

    return matches, exceptions
