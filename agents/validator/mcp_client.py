"""Sync wrapper around the policy MCP server (stdio transport).

The Validator's policy lookups go through MCP — the same server LM Studio or
Claude Desktop could mount — rather than importing the DB layer directly.
Falls back to the local PolicyStore if the MCP subprocess cannot start.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from db.policies import PolicyStore

logger = logging.getLogger(__name__)

SERVER_SCRIPT = Path(__file__).resolve().parent.parent.parent / "mcp_server" / "policy_server.py"


async def _call_tool(tool: str, arguments: dict) -> dict | list | None:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, arguments=arguments)
            if result.structuredContent is not None:
                # FastMCP wraps non-dict results under "result"
                return result.structuredContent.get("result", result.structuredContent)
            return None


class PolicyMCPClient:
    """One MCP tool call per method; degrades to the in-process store."""

    def __init__(self):
        self._fallback = PolicyStore()

    def get_policy(self, policy_number: str) -> dict | None:
        try:
            policy = asyncio.run(_call_tool("get_policy", {"policy_number": policy_number}))
            if isinstance(policy, dict) and "error" not in policy:
                return policy
            return None
        except Exception as exc:
            logger.warning("MCP call failed (%s) — using direct policy store", exc)
            return self._fallback.get_policy(policy_number)

    def get_validation_rules(self) -> list[dict]:
        try:
            rules = asyncio.run(_call_tool("get_validation_rules", {}))
            if isinstance(rules, list):
                return rules
        except Exception as exc:
            logger.warning("MCP call failed (%s) — using direct policy store", exc)
        return self._fallback.get_rules()
