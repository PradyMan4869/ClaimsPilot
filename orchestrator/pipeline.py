"""Orchestrator — pure A2A client.

Delegation happens over the protocol (`message/send` to each agent's URL after
Agent Card discovery), never by importing agent code. The whole chain is one
LangSmith trace; each A2A handoff is a child run with per-agent latency.

Emits `StepEvent`s so the UI can show live progress.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Iterator

from langsmith import traceable

from a2a_lib.client import A2AClient
from common.config import settings
from common.schemas import ExtractedClaim, ResponseLetter, ValidationResult


@dataclass
class StepEvent:
    agent: str
    status: str  # "started" | "completed" | "failed"
    detail: str
    elapsed_s: float = 0.0


@dataclass
class PipelineResult:
    context_id: str
    extracted: ExtractedClaim | None = None
    validation: ValidationResult | None = None
    response: ResponseLetter | None = None
    events: list[StepEvent] = field(default_factory=list)
    error: str | None = None

    @property
    def decision(self) -> str:
        return self.response.decision if self.response else "error"


class ClaimsOrchestrator:
    def __init__(self):
        self.extractor = A2AClient(settings.extractor_url)
        self.validator = A2AClient(settings.validator_url)
        self.responder = A2AClient(settings.responder_url)

    def discover(self) -> dict[str, str]:
        """Fetch all three Agent Cards — the A2A discovery handshake."""
        cards = {}
        for client in (self.extractor, self.validator, self.responder):
            card = client.fetch_card()
            cards[card.name] = f"{card.url} (protocol v{card.protocolVersion})"
        return cards

    @traceable(name="claims_pipeline", run_type="chain")
    def run(self, document_text: str, on_event: Callable[[StepEvent], None] | None = None) -> PipelineResult:
        result = PipelineResult(context_id=uuid.uuid4().hex)

        def emit(event: StepEvent) -> None:
            result.events.append(event)
            if on_event:
                on_event(event)

        try:
            payload = self._step(
                emit, "extractor", self.extractor,
                {"text": document_text}, result.context_id,
            )
            result.extracted = ExtractedClaim.model_validate(payload)

            payload = self._step(
                emit, "validator", self.validator,
                result.extracted.model_dump(), result.context_id,
            )
            result.validation = ValidationResult.model_validate(payload)

            payload = self._step(
                emit, "responder", self.responder,
                result.validation.model_dump(), result.context_id,
            )
            result.response = ResponseLetter.model_validate(payload)
        except Exception as exc:
            result.error = str(exc)
            emit(StepEvent(agent="orchestrator", status="failed", detail=str(exc)))
        return result

    @staticmethod
    @traceable(name="a2a_handoff", run_type="chain")
    def _step(emit, name: str, client: A2AClient, payload: dict, context_id: str) -> dict:
        emit(StepEvent(agent=name, status="started", detail=f"A2A message/send → {client.base_url}"))
        start = time.perf_counter()
        reply = client.send_data(payload, context_id=context_id)
        elapsed = time.perf_counter() - start
        emit(StepEvent(agent=name, status="completed",
                       detail=f"reply received ({len(str(reply))} bytes)", elapsed_s=round(elapsed, 2)))
        return reply
