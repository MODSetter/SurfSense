"""Vision LLM resolution must pass explicit per-config ``api_base``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_get_vision_llm_global_openrouter_sets_api_base():
    """Global negative-ID branch forwards the explicit OpenRouter base."""
    from app.services import llm_service

    cfg = {
        "id": -30_001,
        "name": "GPT-4o Vision (OpenRouter)",
        "litellm_provider": "openrouter",
        "model_name": "openai/gpt-4o",
        "api_key": "sk-or-test",
        "api_base": "https://openrouter.ai/api/v1",
        "api_version": None,
        "litellm_params": {},
        "billing_tier": "free",
    }

    search_space = MagicMock()
    search_space.id = 1
    search_space.user_id = "user-x"
    search_space.vision_llm_config_id = cfg["id"]

    session = AsyncMock()
    scalars = MagicMock()
    scalars.first.return_value = search_space
    result = MagicMock()
    result.scalars.return_value = scalars
    session.execute.return_value = result

    captured: dict = {}

    class FakeSanitized:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    with (
        patch(
            "app.services.vision_llm_router_service.get_global_vision_llm_config",
            return_value=cfg,
        ),
        patch(
            "app.agents.chat.runtime.llm_config.SanitizedChatLiteLLM",
            new=FakeSanitized,
        ),
    ):
        await llm_service.get_vision_llm(session=session, search_space_id=1)

    assert captured.get("api_base") == "https://openrouter.ai/api/v1"
    assert captured["model"] == "openrouter/openai/gpt-4o"


def test_vision_router_deployment_sets_api_base_when_config_empty():
    """Auto-mode vision router carries explicit api_base into deployments."""
    from app.services.vision_llm_router_service import VisionLLMRouterService

    deployment = VisionLLMRouterService._config_to_deployment(
        {
            "model_name": "openai/gpt-4o",
            "litellm_provider": "openrouter",
            "api_key": "sk-or-test",
            "api_base": "https://openrouter.ai/api/v1",
        }
    )
    assert deployment is not None
    assert deployment["litellm_params"]["api_base"] == "https://openrouter.ai/api/v1"
    assert deployment["litellm_params"]["model"] == "openrouter/openai/gpt-4o"
