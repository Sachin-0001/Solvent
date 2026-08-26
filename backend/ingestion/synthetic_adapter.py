"""
Adapters that read the generated synthetic ledger / bank-statement files and
normalize them into the same Transaction shape the RazorpayAdapter produces.
Reconciliation and every downstream stage only ever sees Transaction objects,
never the raw per-source row format.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.ingestion.base import IngestionAdapter, Transaction


class SyntheticLedgerAdapter(IngestionAdapter):
    name = "internal_ledger"

    def __init__(self, path: Path):
        self.path = path

    def fetch(self, **kwargs: Any) -> list[Transaction]:
        rows = json.loads(self.path.read_text())
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


class SyntheticBankAdapter(IngestionAdapter):
    name = "bank_statement"

    def __init__(self, path: Path):
        self.path = path

    def fetch(self, **kwargs: Any) -> list[Transaction]:
        rows = json.loads(self.path.read_text())
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
