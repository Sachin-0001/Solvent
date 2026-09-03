"""
Track B ("connect my account") CSV ingestion — parses a merchant-uploaded
ledger/bank-statement CSV into the same Transaction shape every other adapter
produces (synthetic_adapter.py, db_adapter.py, razorpay_adapter.py), so
reconciliation/tax matching/forecasting/QA don't need to know or care that the
source is a user-uploaded file instead of the synthetic demo dataset.

CSV first (per CLAUDE.md's pdf_adapter.py stretch note — PDF is a documented
future adapter, not built) — expected columns, case-insensitive:

  Ledger CSV : row_id, order_id, amount, timestamp, [payment_method, fee_amount,
               tax_on_fee, refund_amount, status]
  Bank CSV   : row_id, order_id, amount, timestamp, [utr_reference]

`row_id` is auto-generated (LEDGxxxxx / BANKxxxxx) if the column is missing —
real bank exports often don't have a stable row identifier of their own.
Optional columns default to values that make the fields simply inert rather
than wrong: missing fee/tax/refund amounts default to 0, not None, so
exact_match.py's `expected_net` (which already treats a None fee as 0 via
`fee or 0.0`) behaves identically either way.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from backend.ingestion.base import IngestionAdapter, Transaction


class CSVFormatError(ValueError):
    pass


def _read_rows(csv_text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise CSVFormatError("CSV appears to be empty (no header row found).")
    # Normalize header casing/whitespace so "Order ID", "order_id", " order_id "
    # all resolve the same way — real exports are inconsistent about this.
    normalized = {name: name.strip().lower().replace(" ", "_") for name in reader.fieldnames}
    rows = []
    for row in reader:
        rows.append({normalized[k]: v for k, v in row.items() if k in normalized})
    return rows


def _require(row: dict[str, str], field: str, row_num: int) -> str:
    value = row.get(field, "").strip()
    if not value:
        raise CSVFormatError(f"Row {row_num}: missing required column '{field}'.")
    return value


def _float(row: dict[str, str], field: str, default: float = 0.0) -> float:
    value = row.get(field, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _parse_timestamp(value: str, row_num: int) -> str:
    value = value.strip()
    for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            dt = datetime.fromisoformat(value) if fmt is None else datetime.strptime(value, fmt)
            return dt.isoformat()
        except ValueError:
            continue
    raise CSVFormatError(f"Row {row_num}: unrecognized timestamp format '{value}'.")


class CSVLedgerAdapter(IngestionAdapter):
    name = "internal_ledger"

    def __init__(self, csv_text: str):
        self.csv_text = csv_text

    def fetch(self, **kwargs: Any) -> list[Transaction]:
        rows = _read_rows(self.csv_text)
        transactions = []
        for i, row in enumerate(rows, start=1):
            row_id = row.get("row_id", "").strip() or f"LEDG{i:05d}"
            amount = _float(row, "amount")
            if amount == 0.0 and not row.get("amount", "").strip():
                raise CSVFormatError(f"Row {i}: missing required column 'amount'.")
            transactions.append(
                Transaction(
                    source=self.name,
                    source_id=row_id,
                    order_id=row.get("order_id", "").strip() or None,
                    amount=amount,
                    currency="INR",
                    method=row.get("payment_method", "").strip() or None,
                    status=row.get("status", "").strip() or "unknown",
                    fee=_float(row, "fee_amount"),
                    tax_on_fee=_float(row, "tax_on_fee"),
                    settled_at=None,
                    created_at=_parse_timestamp(_require(row, "timestamp", i), i),
                    raw={
                        "tax_on_fee": _float(row, "tax_on_fee"),
                        "refund_amount": _float(row, "refund_amount"),
                    },
                )
            )
        return transactions


class CSVBankAdapter(IngestionAdapter):
    name = "bank_statement"

    def __init__(self, csv_text: str):
        self.csv_text = csv_text

    def fetch(self, **kwargs: Any) -> list[Transaction]:
        rows = _read_rows(self.csv_text)
        transactions = []
        for i, row in enumerate(rows, start=1):
            row_id = row.get("row_id", "").strip() or f"BANK{i:05d}"
            ts = _parse_timestamp(_require(row, "timestamp", i), i)
            transactions.append(
                Transaction(
                    source=self.name,
                    source_id=row_id,
                    order_id=row.get("order_id", "").strip() or None,
                    amount=_float(row, "amount"),
                    currency="INR",
                    method=None,
                    status="credited",
                    fee=None,
                    tax_on_fee=None,
                    settled_at=ts,
                    created_at=ts,
                    raw={"utr_reference": row.get("utr_reference", "").strip() or None},
                )
            )
        return transactions


def detect_date_range(transactions: list[Transaction]) -> dict[str, str] | None:
    if not transactions:
        return None
    dates = [datetime.fromisoformat(t.created_at) for t in transactions]
    return {"start": min(dates).date().isoformat(), "end": max(dates).date().isoformat()}
