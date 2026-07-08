"""A2A protocol round-trip: real client against an in-process ASGI agent."""
import asyncio

import httpx
import pytest

from a2a_lib.client import A2AClient, A2AClientError
from a2a_lib.models import AgentCard, AgentSkill
from a2a_lib.server import create_agent_app


class SyncASGITransport(httpx.BaseTransport):
    """Sync adapter for httpx.ASGITransport (async-only since httpx 0.28)."""

    def __init__(self, app):
        self._transport = httpx.ASGITransport(app=app)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return asyncio.run(self._handle(request))

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        response = await self._transport.handle_async_request(request)
        content = await response.aread()
        await response.aclose()
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=content,
            request=request,
        )

CARD = AgentCard(
    name="echo-agent",
    description="test agent",
    url="http://testserver",
    skills=[AgentSkill(id="echo", name="Echo", description="echoes payloads")],
)


def make_client(handler) -> A2AClient:
    app = create_agent_app(CARD, handler)
    return A2AClient("http://testserver", transport=SyncASGITransport(app))


def test_agent_card_discovery():
    client = make_client(lambda payload: payload)
    card = client.fetch_card()
    assert card.name == "echo-agent"
    assert card.protocolVersion == "1.0"
    assert card.skills[0].id == "echo"


def test_data_round_trip():
    client = make_client(lambda payload: {"echoed": payload})
    reply = client.send_data({"claim_amount": 5000})
    assert reply == {"echoed": {"claim_amount": 5000}}


def test_context_id_flows_through():
    seen = {}

    def handler(payload):
        return {"ok": True}

    app = create_agent_app(CARD, handler)
    client = A2AClient("http://testserver", transport=SyncASGITransport(app))
    reply = client.send_data({"x": 1}, context_id="ctx-42")
    assert reply == {"ok": True}


def test_handler_error_becomes_jsonrpc_error():
    def handler(payload):
        raise ValueError("boom")

    client = make_client(handler)
    with pytest.raises(A2AClientError, match="boom"):
        client.send_data({"x": 1})


def test_unknown_method_rejected():
    app = create_agent_app(CARD, lambda p: p)
    http = httpx.Client(transport=SyncASGITransport(app), base_url="http://testserver")
    response = http.post("/", json={"jsonrpc": "2.0", "id": "1", "method": "tasks/get", "params": {}})
    assert response.json()["error"]["code"] == -32601
