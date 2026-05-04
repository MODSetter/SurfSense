"""Defense-in-depth: image-gen call sites must not let an empty
``api_base`` fall through to LiteLLM's module-global ``litellm.api_base``.

The bug repro: an OpenRouter image-gen config ships
``api_base=""``. The pre-fix call site in
``image_generation_routes._execute_image_generation`` did
``if cfg.get("api_base"): kwargs["api_base"] = cfg["api_base"]`` which
silently dropped the empty string. LiteLLM then fell back to
``litellm.api_base`` (commonly inherited from ``AZURE_OPENAI_ENDPOINT``)
and OpenRouter's ``image_generation/transformation`` appended
``/chat/completions`` to it → 404 ``Resource not found``.

This test pins the post-fix behaviour: with an empty ``api_base`` in
the config, the call site MUST set ``api_base`` to OpenRouter's public
URL instead of leaving it unset.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_global_openrouter_image_gen_sets_api_base_when_config_empty():
    """The global-config branch (``config_id < 0``) of
    ``_execute_image_generation`` must apply the resolver and pin
    ``api_base`` to OpenRouter when the config ships an empty string.
    """
    from app.routes import image_generation_routes

    cfg = {
        "id": -20_001,
        "name": "GPT Image 1 (OpenRouter)",
        "provider": "OPENROUTER",
        "model_name": "openai/gpt-image-1",
        "api_key": "sk-or-test",
        "api_base": "",  # the original bug shape
        "api_version": None,
        "litellm_params": {},
    }

    captured: dict = {}

    async def fake_aimage_generation(**kwargs):
        captured.update(kwargs)
        return MagicMock(model_dump=lambda: {"data": []}, _hidden_params={})

    image_gen = MagicMock()
    image_gen.image_generation_config_id = cfg["id"]
    image_gen.prompt = "test"
    image_gen.n = 1
    image_gen.quality = None
    image_gen.size = None
    image_gen.style = None
    image_gen.response_format = None
    image_gen.model = None

    search_space = MagicMock()
    search_space.image_generation_config_id = cfg["id"]
    session = MagicMock()

    with (
        patch.object(
            image_generation_routes,
            "_get_global_image_gen_config",
            return_value=cfg,
        ),
        patch.object(
            image_generation_routes,
            "aimage_generation",
            side_effect=fake_aimage_generation,
        ),
    ):
        await image_generation_routes._execute_image_generation(
            session=session, image_gen=image_gen, search_space=search_space
        )

    # The whole point of the fix: even with empty ``api_base`` in the
    # config, we forward OpenRouter's public URL so the call doesn't
    # inherit an Azure endpoint.
    assert captured.get("api_base") == "https://openrouter.ai/api/v1"
    assert captured["model"] == "openrouter/openai/gpt-image-1"


@pytest.mark.asyncio
async def test_generate_image_tool_global_sets_api_base_when_config_empty():
    """Same defense at the agent tool entry point — both surfaces share
    the same OpenRouter config payloads."""
    from app.agents.new_chat.tools import generate_image as gi_module

    cfg = {
        "id": -20_001,
        "name": "GPT Image 1 (OpenRouter)",
        "provider": "OPENROUTER",
        "model_name": "openai/gpt-image-1",
        "api_key": "sk-or-test",
        "api_base": "",
        "api_version": None,
        "litellm_params": {},
    }

    captured: dict = {}

    async def fake_aimage_generation(**kwargs):
        captured.update(kwargs)
        response = MagicMock()
        response.model_dump.return_value = {
            "data": [{"url": "https://example.com/x.png"}]
        }
        response._hidden_params = {"model": "openrouter/openai/gpt-image-1"}
        return response

    search_space = MagicMock()
    search_space.id = 1
    search_space.image_generation_config_id = cfg["id"]

    session_cm = AsyncMock()
    session = AsyncMock()
    session_cm.__aenter__.return_value = session

    scalars = MagicMock()
    scalars.first.return_value = search_space
    exec_result = MagicMock()
    exec_result.scalars.return_value = scalars
    session.execute.return_value = exec_result
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    # ``refresh(db_image_gen)`` needs to populate ``id`` for token URL fallback.
    async def _refresh(obj):
        obj.id = 1

    session.refresh.side_effect = _refresh

    with (
        patch.object(gi_module, "shielded_async_session", return_value=session_cm),
        patch.object(gi_module, "_get_global_image_gen_config", return_value=cfg),
        patch.object(
            gi_module, "aimage_generation", side_effect=fake_aimage_generation
        ),
        patch.object(
            gi_module, "is_image_gen_auto_mode", side_effect=lambda cid: cid == 0
        ),
    ):
        tool = gi_module.create_generate_image_tool(
            search_space_id=1, db_session=MagicMock()
        )
        await tool.ainvoke({"prompt": "a cat", "n": 1})

    assert captured.get("api_base") == "https://openrouter.ai/api/v1"
    assert captured["model"] == "openrouter/openai/gpt-image-1"


def test_image_gen_router_deployment_sets_api_base_when_config_empty():
    """The Auto-mode router pool must also resolve ``api_base`` when an
    OpenRouter config ships an empty string. The deployment dict is fed
    straight to ``litellm.Router``, so a missing ``api_base`` would
    leak the same way as the direct call sites.
    """
    from app.services.image_gen_router_service import ImageGenRouterService

    deployment = ImageGenRouterService._config_to_deployment(
        {
            "model_name": "openai/gpt-image-1",
            "provider": "OPENROUTER",
            "api_key": "sk-or-test",
            "api_base": "",
        }
    )
    assert deployment is not None
    assert deployment["litellm_params"]["api_base"] == "https://openrouter.ai/api/v1"
    assert deployment["litellm_params"]["model"] == "openrouter/openai/gpt-image-1"
