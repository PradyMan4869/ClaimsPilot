"""LM Studio client (OpenAI-compatible) with a JSON-extraction helper."""
from __future__ import annotations

import json
import logging
import re

from openai import OpenAI, OpenAIError

from common.config import settings

logger = logging.getLogger(__name__)


class LocalLLM:
    def __init__(self):
        self.client = OpenAI(
            base_url=settings.lmstudio_base_url,
            api_key=settings.lmstudio_api_key,
            timeout=120,
        )
        self.model = settings.lmstudio_model

    def is_available(self) -> bool:
        try:
            self.client.models.list()
            return True
        except OpenAIError:
            return False

    def complete(self, system: str, user: str, temperature: float = 0.2) -> str | None:
        # Mistral-family chat templates reject the system role, so the
        # system prompt is folded into the user turn — semantically
        # equivalent and compatible with every LM Studio model.
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": f"{system}\n\n{user}"},
                ],
                temperature=temperature,
                max_tokens=800,
            )
            return response.choices[0].message.content
        except OpenAIError as exc:
            logger.warning("LM Studio call failed: %s", exc)
            return None

    def complete_json(self, system: str, user: str) -> dict | None:
        """Completion that must yield a JSON object; tolerates fenced/wrapped output."""
        raw = self.complete(system + "\nRespond with a single JSON object only.", user)
        if raw is None:
            return None
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            logger.warning("No JSON object in LLM output: %.200s", raw)
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            logger.warning("Malformed JSON from LLM: %s", exc)
            return None
