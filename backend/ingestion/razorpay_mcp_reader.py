"""
Reads Razorpay settlement/payment/refund data via Razorpay's official Remote
MCP Server (https://mcp.razorpay.com/mcp) instead of the `razorpay` Python SDK
that razorpay_adapter.py uses. This is a separate, additive reader — it does
not replace razorpay_adapter.py, and nothing downstream (reconciliation, tax
matcher, forecaster) changes: it's exactly the same IngestionAdapter-shaped
output, from a different transport.

Only tools confirmed to support the Remote server are used here (checked
against the live README table at
https://github.com/razorpay/razorpay-mcp-server, Remote Server Support
column, 2026-09-02):
  - fetch_all_settlements       -> Remote: yes
  - fetch_all_payments          -> Remote: yes
  - fetch_all_refunds           -> Remote: yes
`create_refund` and `create_instant_settlement` are Local-only and are not
used here — this reader is read-only by design anyway (ingestion never needs
to create anything on the merchant's account).

Auth: the Remote MCP Server takes a merchant token, not raw key/secret —
base64(RAZORPAY_KEY_ID:RAZORPAY_KEY_SECRET), sent as
`Authorization: Basic <token>` (see the MCP server's README "Authentication"
section). Built here from the same backend/config.py credentials
razorpay_adapter.py already uses, so nothing new needs to be configured.
"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import httpx
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client

from backend.config import require_razorpay_keys

MCP_SERVER_URL = "https://mcp.razorpay.com/mcp"


def _merchant_token() -> str:
    key_id, key_secret = require_razorpay_keys()
    return base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()


def _parse_tool_result(result: types.CallToolResult) -> Any:
    """MCP tool results carry their payload as a list of content blocks (text
    JSON, typically). Concatenate text blocks and parse as JSON; fall back to
    raw text if a tool ever returns something non-JSON."""
    text = "".join(block.text for block in result.content if isinstance(block, types.TextContent))
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text


async def _call_tool(name: str, arguments: dict[str, Any]) -> Any:
    headers = {"Authorization": f"Basic {_merchant_token()}"}
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as http_client:
        async with streamable_http_client(MCP_SERVER_URL, http_client=http_client) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                if result.is_error:
                    raise RuntimeError(f"MCP tool {name} returned an error: {_parse_tool_result(result)}")
                return _parse_tool_result(result)


async def fetch_settlements(count: int = 20) -> list[dict[str, Any]]:
    data = await _call_tool("fetch_all_settlements", {"count": count})
    return data.get("items", []) if isinstance(data, dict) else []


async def fetch_payments(count: int = 20) -> list[dict[str, Any]]:
    data = await _call_tool("fetch_all_payments", {"count": count})
    return data.get("items", []) if isinstance(data, dict) else []


async def fetch_refunds(count: int = 20) -> list[dict[str, Any]]:
    data = await _call_tool("fetch_all_refunds", {"count": count})
    return data.get("items", []) if isinstance(data, dict) else []


async def fetch_all(count: int = 20) -> dict[str, list[dict[str, Any]]]:
    """Fetches settlements, payments, and refunds concurrently over one MCP
    session each (the SDK's ClientSession isn't safe to share across
    concurrent calls, so each tool gets its own short-lived connection)."""
    settlements, payments, refunds = await asyncio.gather(
        fetch_settlements(count), fetch_payments(count), fetch_refunds(count)
    )
    return {"settlements": settlements, "payments": payments, "refunds": refunds}


def main() -> None:
    result = asyncio.run(fetch_all())
    print("=== Razorpay Remote MCP reader ===")
    print(f"Server: {MCP_SERVER_URL}")
    for key, items in result.items():
        print(f"\n{key}: {len(items)} item(s)")
        for item in items[:3]:
            print(f"  {item}")


if __name__ == "__main__":
    main()
