"""Central configuration — every tunable comes from the environment."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    # LM Studio
    lmstudio_base_url: str = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    lmstudio_model: str = os.getenv("LMSTUDIO_MODEL", "local-model")
    lmstudio_api_key: str = os.getenv("LMSTUDIO_API_KEY", "lm-studio")

    # MongoDB
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db: str = os.getenv("MONGO_DB", "claimspilot")

    # Agent network
    agent_host: str = os.getenv("AGENT_HOST", "127.0.0.1")
    extractor_port: int = int(os.getenv("EXTRACTOR_PORT", "8101"))
    validator_port: int = int(os.getenv("VALIDATOR_PORT", "8102"))
    responder_port: int = int(os.getenv("RESPONDER_PORT", "8103"))

    # Validator internals
    crewai_enabled: bool = os.getenv("CREWAI_ENABLED", "false").lower() == "true"
    auto_approve_limit: float = float(os.getenv("AUTO_APPROVE_LIMIT", "10000"))

    @property
    def extractor_url(self) -> str:
        return f"http://{self.agent_host}:{self.extractor_port}"

    @property
    def validator_url(self) -> str:
        return f"http://{self.agent_host}:{self.validator_port}"

    @property
    def responder_url(self) -> str:
        return f"http://{self.agent_host}:{self.responder_port}"


settings = Settings()
