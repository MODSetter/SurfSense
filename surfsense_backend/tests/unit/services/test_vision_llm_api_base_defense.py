"""Defense-in-depth: vision-LLM resolution must not leak ``api_base``
defaults from ``litellm.api_base`` either.

Vision shares the same shape as image-gen — global YAML / OpenRouter
dynamic configs ship ``api_base=""`` and the pre-fix ``get_vision_llm``
call sites would silently drop the empty string and inherit
``AZURE_OPENAI_ENDPOINT``. ``ChatLiteLLM(...)`` doesn't 404 on
construction so we test the kwargs we hand to it instead.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_get_vision_llm_global_openrouter_sets_api_base():
    """Global negative-ID branch: an OpenRouter vision config with
    ``api_base=""`` must end up calling ``SanitizedChatLiteLLM`` with
    ``api_base="https://openrouter.ai/api/v1"`` — never an empty string,
    never silently absent."""
    from app.services import llm_service

    cfg = {
        "id": -30_001,
        "name": "GPT-4o Vision (OpenRouter)",
        "provider": "OPENROUTER",
        "model_name": "openai/gpt-4o",
        "api_key": "sk-or-test",
        "api_base": "",
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
            "app.agents.new_chat.llm_config.SanitizedChatLiteLLM",
            new=FakeSanitized,
        ),
    ):
        await llm_service.get_vision_llm(session=session, search_space_id=1)

    assert captured.get("api_base") == "https://openrouter.ai/api/v1"
    assert captured["model"] == "openrouter/openai/gpt-4o"


def test_vision_router_deployment_sets_api_base_when_config_empty():
    """Auto-mode vision router: deployments are fed to ``litellm.Router``,
    so the resolver has to apply at deployment construction time too."""
    from app.services.vision_llm_router_service import VisionLLMRouterService

    deployment = VisionLLMRouterService._config_to_deployment(
        {
            "model_name": "openai/gpt-4o",
            "provider": "OPENROUTER",
            "api_key": "sk-or-test",
            "api_base": "",
        }
    )
    assert deployment is not None
    assert deployment["litellm_params"]["api_base"] == "https://openrouter.ai/api/v1"
    assert deployment["litellm_params"]["model"] == "openrouter/openai/gpt-4o"
