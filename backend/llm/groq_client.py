"""
Single shared entry point for every Groq call in this codebase.

Nothing outside this module may import the `groq` SDK directly — that rule keeps
model choice, retry behavior, and JSON-repair logic in exactly one place. Every
other module (reconciliation exception reasoning, tax matcher fallback, Q&A agent,
synthetic data augmentation) calls `call_groq()` or `call_groq_json()`.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from groq import APIConnectionError, APIStatusError, Groq, GroqError, RateLimitError

from backend.config import GROQ_MODEL, require_groq_key

# Re-exported so callers can catch one exception family for "the Groq call
# itself failed" (rate limit, network, auth, 5xx, ...) alongside ValueError
# ("Groq responded but not with parseable JSON") from call_groq_json below.
__all__ = ["call_groq", "call_groq_json", "call_groq_with_tools", "GroqError"]

_client: Groq | None = None

MAX_RETRIES = 2
BASE_BACKOFF_SECONDS = 1.5
RATE_LIMIT_MAX_WAIT_SECONDS = 8.0


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=require_groq_key())
    return _client


def call_groq(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    reasoning_effort: str = "low",
) -> str:
    """Raw text completion. Everything else in this module builds on this.

    The default model (openai/gpt-oss-120b on Groq) is a reasoning model: it
    spends completion tokens on hidden reasoning before the visible answer, so
    `max_tokens` must leave headroom beyond just the answer length, and
    `reasoning_effort` is kept low by default to avoid starving short answers.

    Transient failures (connection errors, 5xx) get a short exponential-backoff
    retry. RateLimitError reads the API's own `Retry-After` header: a short wait
    (<= RATE_LIMIT_MAX_WAIT_SECONDS, typical of a per-minute request-count cap
    from firing batches back-to-back) gets retried; a long wait (a "tokens per
    day" exhaustion, often 10+ minutes) fails fast instead of blocking a batch
    pipeline for that long — the caller's documented fallback (template text /
    honest "unresolved" exception) takes over immediately in that case.
    On final failure this raises groq.GroqError (or a subclass) — callers
    should catch `GroqError` from this module alongside ValueError.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error: GroqError | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = _get_client().chat.completions.create(
                model=model or GROQ_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
            )
            return response.choices[0].message.content or ""
        except RateLimitError as e:
            retry_after = _parse_retry_after(e)
            if (
                attempt < MAX_RETRIES
                and retry_after is not None
                and retry_after <= RATE_LIMIT_MAX_WAIT_SECONDS
            ):
                time.sleep(retry_after)
                last_error = e
                continue
            raise
        except (APIConnectionError, APIStatusError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(BASE_BACKOFF_SECONDS * (2**attempt))
                continue
            raise

    raise last_error  # unreachable, satisfies type checkers


def call_groq_with_tools(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    reasoning_effort: str = "low",
):
    """One turn of a tool-calling conversation: returns the raw Groq message
    object (which may carry `.tool_calls` for the caller's agent loop to
    execute, or plain `.content` as the final answer). Retry policy mirrors
    `call_groq` — this is the only other shape of Groq call in the codebase,
    so it stays in this one shared module rather than duplicating retry
    logic at the call site (backend/qa_agent/agent.py)."""
    last_error: GroqError | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = _get_client().chat.completions.create(
                model=model or GROQ_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
            )
            return response.choices[0].message
        except RateLimitError as e:
            retry_after = _parse_retry_after(e)
            if (
                attempt < MAX_RETRIES
                and retry_after is not None
                and retry_after <= RATE_LIMIT_MAX_WAIT_SECONDS
            ):
                time.sleep(retry_after)
                last_error = e
                continue
            raise
        except (APIConnectionError, APIStatusError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(BASE_BACKOFF_SECONDS * (2**attempt))
                continue
            raise

    raise last_error  # unreachable, satisfies type checkers


def _parse_retry_after(error: RateLimitError) -> float | None:
    """Reads the Retry-After header Groq sends on 429s. Returns None if
    unavailable, in which case we don't guess — fail fast per the docstring."""
    try:
        header = error.response.headers.get("retry-after")
        return float(header) if header is not None else None
    except (AttributeError, ValueError):
        return None


def _extract_json_block(text: str) -> str:
    """Strip markdown code fences and surrounding prose, leaving the JSON body."""
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    # Fall back to the outermost {...} or [...] span.
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1].strip()

    return text.strip()


def _repair_json(raw: str) -> str:
    """Best-effort cleanup for common small LLM JSON mistakes."""
    repaired = raw
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)  # trailing commas
    repaired = repaired.replace("“", '"').replace("”", '"')  # smart quotes
    repaired = repaired.replace("‘", "'").replace("’", "'")
    repaired = re.sub(r"'([A-Za-z0-9_]+?)'\s*:", r'"\1":', repaired)  # 'key': -> "key":
    return repaired


def call_groq_json(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 1024,
    retries: int = 2,
) -> Any:
    """
    Completion that returns parsed JSON. Handles markdown fences, stray prose, and
    common malformed-JSON patterns before giving up. Raises ValueError if no
    attempt (including retries with an explicit "return valid JSON only" nudge)
    produces parseable JSON.
    """
    json_system = (
        (system + "\n\n" if system else "")
        + "Respond with valid JSON only. No markdown fences, no commentary."
    )

    last_error: Exception | None = None
    last_raw = ""
    for attempt in range(retries + 1):
        raw = call_groq(
            prompt if attempt == 0 else prompt + "\n\nReturn ONLY valid JSON, nothing else.",
            system=json_system,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        last_raw = raw
        candidate = _extract_json_block(raw)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            try:
                return json.loads(_repair_json(candidate))
            except json.JSONDecodeError as e2:
                last_error = e2
                continue

    raise ValueError(
        f"Groq did not return parseable JSON after {retries + 1} attempts. "
        f"Last raw response: {last_raw!r}"
    ) from last_error
