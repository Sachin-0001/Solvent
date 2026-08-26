"""
DB-backed ledger/bank adapters — same IngestionAdapter interface as
synthetic_adapter.py's file-based versions, but sourcing rows from the indexed
Postgres tables ingestion wrote to, instead of re-reading and re-parsing the
entire raw JSON file on every call. This is the adapter pattern actually
earning its keep: downstream code (the reconciliation engine) doesn't change
at all when the source implementation swaps from "parse this file" to
"query this indexed table."
"""

from __future__ import annotations

from typing import Any

from backend import db
from backend.ingestion.base import IngestionAdapter, Transaction


class DBLedgerAdapter(IngestionAdapter):
    name = "internal_ledger"

    def fetch(self, **kwargs: Any) -> list[Transaction]:
        rows = db.load_ledger_rows()
        return [
            Transaction(
                source=self.name,
                source_id=row["row_id"],
                order_id=row.get("order_id"),
                amount=row["amount"],
                currency="INR",
                method=row.get("payment_method"),
                status=row.get("status", "unknown"),
                fee=row.get("fee_amount"),
                tax_on_fee=None,
                settled_at=None,
                created_at=row["timestamp"],
                narration=row.get("narration"),
                raw=row,
            )
            for row in rows
        ]


class DBBankAdapter(IngestionAdapter):
    name = "bank_statement"

    def fetch(self, **kwargs: Any) -> list[Transaction]:
        rows = db.load_bank_rows()
        return [
            Transaction(
                source=self.name,
                source_id=row["row_id"],
                order_id=row.get("order_id"),
                amount=row["amount"],
                currency="INR",
                method=None,
                status="credited",
                fee=None,
                tax_on_fee=None,
                settled_at=row["timestamp"],
                created_at=row["timestamp"],
                narration=row.get("narration"),
                raw=row,
            )
            for row in rows
        ]
