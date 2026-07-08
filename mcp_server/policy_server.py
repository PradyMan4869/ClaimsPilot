"""MCP server exposing the policy store (MongoDB) as tools.

The Validator agent consumes these tools over stdio; any MCP-capable host
(LM Studio, Claude Desktop) can also mount this server.

Run standalone:  python mcp_server/policy_server.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP

from db.policies import PolicyStore

mcp = FastMCP("claimspilot-policies")
store = PolicyStore()


@mcp.tool()
def get_policy(policy_number: str) -> dict:
    """Fetch a policy record (status, coverage window, limit, covered incident types)."""
    policy = store.get_policy(policy_number)
    return policy if policy else {"error": f"policy {policy_number} not found"}


@mcp.tool()
def get_validation_rules() -> list[dict]:
    """List the coverage rules every claim is validated against."""
    return store.get_rules()


if __name__ == "__main__":
    mcp.run(transport="stdio")
