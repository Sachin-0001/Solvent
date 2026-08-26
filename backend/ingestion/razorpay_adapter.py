"""
Live Razorpay test-mode adapter. Walks Orders -> Payments -> Settlements via the
official `razorpay` Python SDK and normalizes each payment into a Transaction.

Test-mode settlements on a fresh account are often empty (Razorpay batches real
settlements on a schedule), so `settled_at` / `fee` may be None for payments that
haven't been swept into a settlement yet. That's expected, not a bug — the
reconciliation engine's exception path is exactly what should handle it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import razorpay

from backend.config import require_razorpay_keys
from backend.ingestion.base import IngestionAdapter, Transaction


def _unix_to_iso(value: Any) -> str | None:
    """Razorpay timestamps are Unix epoch seconds (ints), not ISO strings."""
    if value is None:
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()


PAGE_SIZE = 100  # Razorpay's hard max for `count` per list call


class RazorpayAdapter(IngestionAdapter):
    name = "razorpay"

    def __init__(self) -> None:
        key_id, key_secret = require_razorpay_keys()
        self.client = razorpay.Client(auth=(key_id, key_secret))

    def _paginate(self, list_fn, max_total: int) -> list[dict[str, Any]]:
        """Razorpay list endpoints cap `count` at 100/call and return only that
        page — fetching once silently truncates any account with >100 records.
        Pages via `skip` until a short page (or max_total) ends the walk."""
        items: list[dict[str, Any]] = []
        skip = 0
        while len(items) < max_total:
            page = list_fn({"count": PAGE_SIZE, "skip": skip})["items"]
            items.extend(page)
            if len(page) < PAGE_SIZE:
                break
            skip += PAGE_SIZE
        return items[:max_total]

    def _fetch_orders(self, max_total: int) -> list[dict[str, Any]]:
        return self._paginate(self.client.order.all, max_total)

    def _fetch_payments_for_order(self, order_id: str) -> list[dict[str, Any]]:
        # Payments-per-order rarely exceeds a page, but paginate defensively
        # for merchants with many retried payment attempts on one order.
        return self._paginate(lambda params: self.client.order.payments(order_id, params), 1000)

    def _fetch_settlements(self, max_total: int) -> list[dict[str, Any]]:
        try:
            return self._paginate(self.client.settlement.all, max_total)
        except Exception:
            # Some test accounts don't have settlement API access enabled; treat
            # as "no settlement data yet" rather than failing ingestion.
            return []

    def fetch(self, order_count: int = 100, **kwargs: Any) -> list[Transaction]:
        orders = self._fetch_orders(order_count)
        settlements = self._fetch_settlements(order_count)
        settlement_by_id = {s["id"]: s for s in settlements}

        transactions: list[Transaction] = []
        for order in orders:
            payments = self._fetch_payments_for_order(order["id"])
            for payment in payments:
                settlement_id = payment.get("settlement_id") if isinstance(payment, dict) else None
                settlement = settlement_by_id.get(settlement_id) if settlement_id else None

                transactions.append(
                    Transaction(
                        source=self.name,
                        source_id=payment["id"],
                        order_id=order["id"],
                        amount=payment["amount"] / 100,  # paise -> rupees
                        currency=payment.get("currency", "INR"),
                        method=payment.get("method"),
                        status=payment.get("status", "unknown"),
                        fee=(payment["fee"] / 100) if payment.get("fee") is not None else None,
                        tax_on_fee=(payment["tax"] / 100) if payment.get("tax") is not None else None,
                        settled_at=(
                            _unix_to_iso(settlement["created_at"]) if settlement else None
                        ),
                        created_at=_unix_to_iso(payment.get("created_at")),
                        narration=payment.get("description"),
                        raw={"order": order, "payment": payment, "settlement": settlement},
                    )
                )
        return transactions
