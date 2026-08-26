"""
Single ingestion adapter interface. Every transaction source — the live Razorpay
test-mode feed, the synthetic internal ledger, the synthetic bank statement, and
(future, not yet built) a PDF bank statement — implements this same interface so
the reconciliation engine never needs to know where a record came from.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Transaction:
    """Normalized shape every adapter must emit, regardless of source."""

    source: str  # "razorpay" | "internal_ledger" | "bank_statement"
    source_id: str  # id native to that source (e.g. Razorpay payment id, ledger row id)
    order_id: str | None
    amount: float  # in rupees
    currency: str
    method: str | None  # card, upi, netbanking, wallet, ...
    status: str
    fee: float | None
    tax_on_fee: float | None
    settled_at: str | None  # ISO 8601, None if not yet settled
    created_at: str
    narration: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class IngestionAdapter(ABC):
    """Adapters return a list of Transaction, normalized to the schema above."""

    name: str

    @abstractmethod
    def fetch(self, **kwargs: Any) -> list[Transaction]:
        """Fetch and normalize records from this source."""
        raise NotImplementedError
