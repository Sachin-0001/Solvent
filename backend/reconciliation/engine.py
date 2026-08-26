"""
Orchestrates the three reconciliation tiers in order: exact -> fuzzy -> LLM
exception. Loads ledger/bank data through the ingestion adapters (source-agnostic
— works the same whether the data came from Postgres, a raw file, or a future
live source), so this module has no idea it's looking at synthetic data.
"""

from __future__ import annotations

from dataclasses import asdict

from backend.ingestion.db_adapter import DBBankAdapter, DBLedgerAdapter
from backend.reconciliation.exact_match import MatchResult, exact_match
from backend.reconciliation.fuzzy_match import fuzzy_match
from backend.reconciliation.llm_exception import ExceptionResult, llm_exception_pass


def run_reconciliation() -> dict:
    ledger_txns = DBLedgerAdapter().fetch()
    bank_txns = DBBankAdapter().fetch()

    exact_matches, rem_ledger, rem_bank = exact_match(ledger_txns, bank_txns)
    fuzzy_matches, rem_ledger, rem_bank = fuzzy_match(rem_ledger, rem_bank)
    llm_matches, exceptions = llm_exception_pass(rem_ledger, rem_bank)

    all_matches: list[MatchResult] = exact_matches + fuzzy_matches + llm_matches

    return {
        "matches": all_matches,
        "exceptions": exceptions,
        "tier_counts": {
            "exact": len(exact_matches),
            "fuzzy": len(fuzzy_matches),
            "llm": len(llm_matches),
        },
        "total_ledger_rows": len(ledger_txns),
        "total_bank_rows": len(bank_txns),
    }


def matches_to_dicts(matches: list[MatchResult]) -> list[dict]:
    return [asdict(m) for m in matches]


def exceptions_to_dicts(exceptions: list[ExceptionResult]) -> list[dict]:
    return [asdict(e) for e in exceptions]
