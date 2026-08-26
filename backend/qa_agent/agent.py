"""
Settlement Q&A agent: retrieves relevant context via retriever.py, then asks
Groq (through the single shared wrapper) to answer in plain language, citing
specific figures from the retrieved context rather than inventing numbers.
"""

from __future__ import annotations

from typing import Any

from backend.llm.groq_client import GroqError, call_groq
from backend.qa_agent.retriever import load_settlement_records, retrieve

SYSTEM_PROMPT = (
    "You are Solvent, a settlement assistant for an Indian payment-aggregator "
    "merchant. Answer the merchant's question using ONLY the context provided "
    "below — reconciled transaction records, tax classifications, aggregate "
    "stats, and (when present) a forecast. Cite specific figures (amounts, "
    "counts, percentages, dates) from the context. If the context doesn't "
    "contain enough information to answer confidently, say so explicitly "
    "rather than guessing. Keep the answer concise and plain-language — this "
    "merchant is not a developer."
)


def _format_context(context: dict[str, Any]) -> str:
    parts = [f"AGGREGATE STATS:\n{context['aggregate_stats']}"]

    if context["records"]:
        parts.append("RELEVANT RECORDS:")
        for r in context["records"]:
            parts.append(
                f"- {r['txn_id']} (order {r['order_id']}): amount=₹{r['txn_amount']}, "
                f"method={r['payment_method']}, status={r['reconciliation_status']}, "
                f"tax_category={r.get('tax_category', 'n/a')}, "
                f"days_to_settle={r.get('days_to_settle')}, "
                f"deduction_pct={r.get('deduction_pct')}, "
                f"had_dispute={r.get('had_dispute_flag')}, "
                f"had_refund={r.get('had_refund')}, "
                f"refund_amount={r.get('refund_amount')}"
                + (
                    f", reconciliation_notes={r['reconciliation_reasons']}"
                    if r.get("reconciliation_reasons")
                    else ""
                )
            )
    else:
        parts.append("RELEVANT RECORDS: none matched this question specifically.")

    if context["forecast"] is not None:
        parts.append(f"\n7-DAY CASH FORECAST:\n{context['forecast']}")

    return "\n".join(parts)


def answer_question(question: str, records: list[dict[str, Any]] | None = None) -> str:
    if records is None:
        records = load_settlement_records()

    context = retrieve(question, records)
    context_text = _format_context(context)

    prompt = f"MERCHANT QUESTION:\n{question}\n\nCONTEXT:\n{context_text}"
    try:
        return call_groq(prompt, system=SYSTEM_PROMPT, max_tokens=700, temperature=0.3)
    except GroqError as e:
        # A real API failure (rate limit, network, auth) should surface as an
        # honest, user-facing message — not a 500, and not a wall of raw
        # context dumped into a chat bubble. Aggregate stats are the one part
        # of the context short and structured enough to still be useful here.
        stats = context["aggregate_stats"]
        return (
            f"I couldn't reach the language model just now ({e.__class__.__name__}) — "
            "please try again shortly. Here's what I can tell you without it: "
            f"{stats['reconciled']}/{stats['total_transactions']} transactions reconciled "
            f"({stats['match_rate_pct']}% match rate), {stats['exceptions']} exceptions, "
            f"{stats['disputed_count']} disputed, {stats['refunded_count']} refunded."
        )
