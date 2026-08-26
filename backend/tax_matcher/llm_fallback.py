"""
LLM fallback for the tax matcher. Called only for records `classify_by_rules`
couldn't resolve (missing or malformed required fields) — never for the whole
dataset. Goes through the single shared Groq wrapper, batched.
"""

from __future__ import annotations

from typing import Any

from backend.llm.groq_client import GroqError, call_groq_json
from backend.tax_matcher.rules import VALID_CATEGORIES, TaxClassification

BATCH_SIZE = 15

SYSTEM_PROMPT = (
    "You are a GST-treatment classifier for an Indian payment-aggregator "
    "merchant's settlement records. Classify each transaction into exactly one "
    "of: taxable_sale, gst_on_fee, exempt, refund_credit_note. A refund of any "
    "size means refund_credit_note. If information is genuinely insufficient to "
    "classify confidently, use category \"unresolved\" and explain why."
)


def _call_llm_batch(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    prompt = (
        "Classify each transaction below. Items:\n"
        f"{items}\n\n"
        'Respond with a JSON object mapping txn_id -> '
        '{"category": "taxable_sale"|"gst_on_fee"|"exempt"|"refund_credit_note"|"unresolved", '
        '"reasoning": short string}.'
    )
    try:
        result = call_groq_json(prompt, system=SYSTEM_PROMPT, max_tokens=2500)
        if isinstance(result, dict):
            return result
    except (ValueError, GroqError):
        pass
    return {}


def classify_by_llm(unresolved_txns: list[dict[str, Any]]) -> list[TaxClassification]:
    results: list[TaxClassification] = []
    for start in range(0, len(unresolved_txns), BATCH_SIZE):
        batch = unresolved_txns[start : start + BATCH_SIZE]
        resolutions = _call_llm_batch(batch)
        for txn in batch:
            res = resolutions.get(txn["txn_id"], {})
            category = res.get("category", "unresolved")
            if category not in VALID_CATEGORIES:
                category = "unresolved"
            results.append(
                TaxClassification(
                    txn["txn_id"],
                    category,
                    "llm",
                    res.get("reasoning", "LLM did not return a usable classification."),
                )
            )
    return results
