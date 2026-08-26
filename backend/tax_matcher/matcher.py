"""
Orchestrates the tax matcher: rules first for the clear-cut majority, LLM
fallback only for what rules can't resolve. Anything the LLM also can't resolve
("unresolved") is surfaced as an honest exception, never hidden.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from backend.tax_matcher.llm_fallback import classify_by_llm
from backend.tax_matcher.rules import TaxClassification, classify_by_rules


def run_tax_matcher(transactions: list[dict[str, Any]]) -> dict:
    rule_results: list[TaxClassification] = []
    unresolved: list[dict[str, Any]] = []

    for txn in transactions:
        result = classify_by_rules(txn)
        if result is not None:
            rule_results.append(result)
        else:
            unresolved.append(txn)

    llm_results = classify_by_llm(unresolved) if unresolved else []

    classifications = rule_results + llm_results
    exceptions = [c for c in llm_results if c.category == "unresolved"]

    return {
        "classifications": classifications,
        "exceptions": exceptions,
        "rule_count": len(rule_results),
        "llm_count": len(llm_results),
        "exception_count": len(exceptions),
    }


def classifications_to_dicts(classifications: list[TaxClassification]) -> list[dict]:
    return [asdict(c) for c in classifications]
