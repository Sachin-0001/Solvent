"""
Settlement Q&A agent — a real tool-calling loop, not a single retrieve-then-
answer call. Groq (via the single shared wrapper) decides which deterministic
Python tool(s) to call and in what order; this module executes them and
feeds results back until Groq returns a final plain-language answer. The LLM
never computes a figure itself — every number comes from a tool's return
value, which is itself deterministic Python (backend/qa_agent/tools.py).

Falls back to the pre-agent single-shot retriever context (`retrieve()`) as
one extra tool-independent piece of context up front, so aggregate stats and
(for forward-looking/cash-position questions) forecast/cash-position figures
are available even if the LLM doesn't think to call a tool for them.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from backend.llm.groq_client import GroqError, call_groq_with_tools
from backend.qa_agent.retriever import load_settlement_records, retrieve
from backend.qa_agent.tools import (
    TOOL_SCHEMAS,
    find_relation,
    generate_audit_report,
    search_invoices,
    search_payments,
    search_settlements,
)

SYSTEM_PROMPT = (
    "You are Solvent, a settlement assistant for an Indian payment-aggregator "
    "merchant. You have tools to search payments, settlements, and tax "
    "classifications ('invoices'), find how a specific order/transaction's "
    "pieces relate to each other, and generate an audit report. Call "
    "whatever tool(s) you need — you may call several in sequence — to "
    "gather the facts before answering. Cite specific figures (amounts, "
    "counts, percentages, dates) exactly as returned by the tools — never "
    "recompute, round differently, or invent a number yourself; all "
    "arithmetic has already been done by the backend. If a tool returns no "
    "match or you still don't have enough information after using the "
    "available tools, say so explicitly rather than guessing. Keep the "
    "final answer concise and plain-language — this merchant is not a "
    "developer."
)

MAX_TOOL_ITERATIONS = 4


@dataclass
class ToolCallTrace:
    name: str
    arguments: dict[str, Any]
    status: str  # "success" | "error"
    result_summary: str
    duration_ms: int


def _tool_dispatch(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "search_payments": lambda **kw: search_payments(records, **kw),
        "search_settlements": lambda **kw: search_settlements(records, **kw),
        "search_invoices": lambda **kw: search_invoices(records, **kw),
        "find_relation": lambda **kw: find_relation(records, **kw),
        "generate_audit_report": lambda **kw: generate_audit_report(records, **kw),
    }


def _summarize_result(result: Any) -> str:
    if isinstance(result, dict):
        if "total_matched" in result:
            return f"{result['total_matched']} matched, {result.get('returned', 0)} returned"
        if "found" in result:
            return "found" if result["found"] else "not found"
        if "total_transactions" in result:
            return f"audit report over {result['total_transactions']} transactions"
    return "ok"


def _run_tool(name: str, arguments: dict[str, Any], dispatch: dict[str, Any]) -> tuple[Any, ToolCallTrace]:
    start = time.monotonic()
    fn = dispatch.get(name)
    if fn is None:
        trace = ToolCallTrace(
            name=name, arguments=arguments, status="error",
            result_summary=f"Unknown tool '{name}'", duration_ms=0,
        )
        return {"error": f"Unknown tool '{name}'"}, trace

    try:
        result = fn(**arguments)
        duration_ms = int((time.monotonic() - start) * 1000)
        trace = ToolCallTrace(
            name=name, arguments=arguments, status="success",
            result_summary=_summarize_result(result), duration_ms=duration_ms,
        )
        return result, trace
    except Exception as e:  # noqa: BLE001 - surfaced as a failed tool-call trace, not a 500
        duration_ms = int((time.monotonic() - start) * 1000)
        trace = ToolCallTrace(
            name=name, arguments=arguments, status="error",
            result_summary=f"{e.__class__.__name__}: {e}", duration_ms=duration_ms,
        )
        return {"error": str(e)}, trace


def _format_seed_context(context: dict[str, Any]) -> str:
    """The pre-agent retrieval pass (semantic search + always-on aggregate
    stats + forecast/cash-position when relevant) is handed to the model as
    starting context, not as ground truth to skip tools — it may still call
    search_* / find_relation / generate_audit_report tools for anything more
    specific than this snapshot covers."""
    parts = [f"AGGREGATE STATS (all transactions):\n{context['aggregate_stats']}"]
    if context["forecast"] is not None:
        parts.append(f"\n7-DAY CASH FORECAST:\n{context['forecast']}")
    if context.get("cash_position") is not None:
        parts.append(f"\nCASH POSITION (current_cash is a demo placeholder):\n{context['cash_position']}")
    return "\n".join(parts)


def answer_question(
    question: str, records: list[dict[str, Any]] | None = None
) -> tuple[str, list[dict[str, Any]]]:
    """Returns (answer_text, trace) where trace is a list of
    {name, arguments, status, result_summary, duration_ms} dicts describing
    every tool call the agent made, in order — for the UI's tool-call log."""
    if records is None:
        records = load_settlement_records()

    seed_context = retrieve(question, records)
    dispatch = _tool_dispatch(records)
    trace: list[ToolCallTrace] = []

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"MERCHANT QUESTION:\n{question}\n\n"
                f"STARTING CONTEXT (may not be enough — use tools for specifics):\n"
                f"{_format_seed_context(seed_context)}"
            ),
        },
    ]

    try:
        for _ in range(MAX_TOOL_ITERATIONS):
            message = call_groq_with_tools(messages, tools=TOOL_SCHEMAS, max_tokens=900)

            if not message.tool_calls:
                answer = message.content or "I wasn't able to produce an answer from the available data."
                return answer, [asdict(t) for t in trace]

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in message.tool_calls
                    ],
                }
            )

            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}

                result, call_trace = _run_tool(tc.function.name, arguments, dispatch)
                trace.append(call_trace)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, default=str),
                    }
                )

        # Exhausted MAX_TOOL_ITERATIONS without a final answer — ask one more
        # time with tools disabled so the model is forced to summarize
        # whatever it has gathered, rather than looping forever.
        final = call_groq_with_tools(messages, tools=[], max_tokens=900)
        answer = final.content or "I gathered some data but couldn't finish reasoning about it — please try rephrasing."
        return answer, [asdict(t) for t in trace]

    except GroqError as e:
        stats = seed_context["aggregate_stats"]
        fallback = (
            f"I couldn't reach the language model just now ({e.__class__.__name__}) — "
            "please try again shortly. Here's what I can tell you without it: "
            f"{stats['reconciled']}/{stats['total_transactions']} transactions reconciled "
            f"({stats['match_rate_pct']}% match rate), {stats['exceptions']} exceptions, "
            f"{stats['disputed_count']} disputed, {stats['refunded_count']} refunded."
        )
        return fallback, [asdict(t) for t in trace]
