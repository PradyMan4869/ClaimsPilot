"""A2A v1.0 protocol types (the subset this pipeline uses).

Spec: https://a2a-protocol.org — agents publish an Agent Card at
`/.well-known/agent-card.json` and exchange Messages composed of Parts via
JSON-RPC 2.0 `message/send`. Structured payloads travel as DataParts.
"""
from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

A2A_PROTOCOL_VERSION = "1.0"
AGENT_CARD_PATH = "/.well-known/agent-card.json"


# --------------------------------------------------------------------------- card
class AgentSkill(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)


class AgentCapabilities(BaseModel):
    streaming: bool = False
    pushNotifications: bool = False
    stateTransitionHistory: bool = False


class AgentCard(BaseModel):
    protocolVersion: str = A2A_PROTOCOL_VERSION
    name: str
    description: str
    url: str
    version: str = "1.0.0"
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    defaultInputModes: list[str] = Field(default_factory=lambda: ["application/json", "text/plain"])
    defaultOutputModes: list[str] = Field(default_factory=lambda: ["application/json", "text/plain"])
    skills: list[AgentSkill] = Field(default_factory=list)


# ------------------------------------------------------------------------ message
class TextPart(BaseModel):
    kind: Literal["text"] = "text"
    text: str


class DataPart(BaseModel):
    kind: Literal["data"] = "data"
    data: dict[str, Any]


Part = TextPart | DataPart


class Message(BaseModel):
    kind: Literal["message"] = "message"
    role: Literal["user", "agent"]
    parts: list[Part]
    messageId: str = Field(default_factory=lambda: uuid.uuid4().hex)
    contextId: str | None = None

    def first_data(self) -> dict[str, Any] | None:
        for part in self.parts:
            if isinstance(part, DataPart):
                return part.data
        return None

    def first_text(self) -> str | None:
        for part in self.parts:
            if isinstance(part, TextPart):
                return part.text
        return None


# ----------------------------------------------------------------------- JSON-RPC
class JSONRPCRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class JSONRPCError(BaseModel):
    code: int
    message: str
    data: Any | None = None


class JSONRPCResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    result: dict[str, Any] | None = None
    error: JSONRPCError | None = None


METHOD_NOT_FOUND = JSONRPCError(code=-32601, message="Method not found")
INVALID_PARAMS = JSONRPCError(code=-32602, message="Invalid params")
INTERNAL_ERROR_CODE = -32603
