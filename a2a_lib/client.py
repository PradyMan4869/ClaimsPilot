"""A2A client: agent-card discovery + message/send over JSON-RPC 2.0."""
from __future__ import annotations

import uuid
from typing import Any

import httpx

from a2a_lib.models import (
    AGENT_CARD_PATH,
    AgentCard,
    DataPart,
    JSONRPCRequest,
    JSONRPCResponse,
    Message,
)


class A2AClientError(RuntimeError):
    pass


class A2AClient:
    """Talks to one remote agent. Discovery first, then typed message exchange."""

    def __init__(self, base_url: str, timeout: float = 300.0,
                 transport: httpx.BaseTransport | None = None):
        # `transport` lets tests mount an in-process ASGI app instead of the network.
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(timeout=timeout, transport=transport)
        self._card: AgentCard | None = None

    def fetch_card(self) -> AgentCard:
        """Discover the agent via its well-known Agent Card."""
        if self._card is None:
            response = self._http.get(self.base_url + AGENT_CARD_PATH)
            response.raise_for_status()
            self._card = AgentCard.model_validate(response.json())
        return self._card

    def send_data(self, payload: dict[str, Any], context_id: str | None = None) -> dict[str, Any]:
        """Send a structured payload (DataPart); return the agent's DataPart reply."""
        message = Message(role="user", parts=[DataPart(data=payload)], contextId=context_id)
        request = JSONRPCRequest(
            id=uuid.uuid4().hex,
            method="message/send",
            params={"message": message.model_dump()},
        )
        response = self._http.post(self.base_url + "/", json=request.model_dump())
        response.raise_for_status()
        rpc = JSONRPCResponse.model_validate(response.json())
        if rpc.error is not None:
            raise A2AClientError(f"{self.base_url}: {rpc.error.code} {rpc.error.message}")
        reply = Message.model_validate(rpc.result)
        data = reply.first_data()
        if data is None:
            raise A2AClientError(f"{self.base_url}: agent reply carried no DataPart")
        return data

    def close(self) -> None:
        self._http.close()
