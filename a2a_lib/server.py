"""A2A server factory.

`create_agent_app(card, handler)` returns a FastAPI app that:
- serves the Agent Card at /.well-known/agent-card.json (discovery), and
- accepts JSON-RPC 2.0 `message/send` at POST /, dispatching to `handler`.

`handler` receives the structured payload (DataPart dict, or {"text": ...} for
text-only messages) and returns a dict, which is wrapped in an agent Message.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from a2a_lib.models import (
    AGENT_CARD_PATH,
    INTERNAL_ERROR_CODE,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    AgentCard,
    DataPart,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    Message,
)

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], dict[str, Any]]


def create_agent_app(card: AgentCard, handler: Handler) -> FastAPI:
    app = FastAPI(title=card.name, description=card.description, version=card.version)

    @app.get(AGENT_CARD_PATH)
    def agent_card() -> AgentCard:
        return card

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "agent": card.name}

    @app.post("/")
    async def rpc(request: JSONRPCRequest) -> JSONResponse:
        if request.method != "message/send":
            return _error(request.id, METHOD_NOT_FOUND)

        try:
            message = Message.model_validate(request.params.get("message", {}))
        except Exception:
            return _error(request.id, INVALID_PARAMS)

        payload = message.first_data()
        if payload is None:
            text = message.first_text()
            if text is None:
                return _error(request.id, INVALID_PARAMS)
            payload = {"text": text}

        try:
            result = handler(payload)
        except Exception as exc:  # agent errors go back as JSON-RPC errors
            logger.exception("%s handler failed", card.name)
            return _error(
                request.id,
                JSONRPCError(code=INTERNAL_ERROR_CODE, message=str(exc)),
            )

        reply = Message(role="agent", parts=[DataPart(data=result)], contextId=message.contextId)
        response = JSONRPCResponse(id=request.id, result=reply.model_dump())
        return JSONResponse(response.model_dump(exclude_none=True))

    return app


def _error(request_id: str | int, error: JSONRPCError) -> JSONResponse:
    response = JSONRPCResponse(id=request_id, error=error)
    return JSONResponse(response.model_dump(exclude_none=True), status_code=200)
