from __future__ import annotations

from app.config import Settings
from app.services.agents import AgentClient
from app.services.agents.mock import MockAgentClient
from app.services.agents.openai import OpenAIAgentClient

SUPPORTED_AI_PROVIDERS = ("mock", "openai", "real")


def build_agent_client(settings: Settings) -> AgentClient:
    provider = settings.ai_provider.strip().lower()
    if provider == "mock":
        return MockAgentClient(settings.fixture_path)
    if provider in {"openai", "real"}:
        if not settings.openai_api_key:
            raise ValueError(f"AI_PROVIDER={provider} requires OPENAI_API_KEY.")
        return OpenAIAgentClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            fallback=MockAgentClient(settings.fixture_path),
        )
    supported = ", ".join(SUPPORTED_AI_PROVIDERS)
    raise ValueError(f"Unsupported AI_PROVIDER '{settings.ai_provider}'. Supported: {supported}.")
