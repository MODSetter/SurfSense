"""Image-gen call sites must pass each config's explicit ``api_base``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain.tools import ToolRuntime

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_global_openrouter_image_gen_sets_explicit_api_base():
    """The global-config branch forwards the explicit OpenRouter base."""
    from app.routes import image_generation_routes

    global_model = {
        "id": -20_001,
        "connection_id": -101,
        "model_id": "openai/gpt-image-1",
        "supports_image_generation": True,
        "capabilities_override": {},
    }
    global_connection = {
        "id": -101,
        "provider": "openrouter",
        "api_key": "sk-or-test",
        "base_url": "https://openrouter.ai/api/v1",
        "extra": {},
    }

    captured: dict = {}

    async def fake_aimage_generation(**kwargs):
        captured.update(kwargs)
        return MagicMock(model_dump=lambda: {"data": []}, _hidden_params={})

    image_gen = MagicMock()
    image_gen.image_gen_model_id = global_model["id"]
    image_gen.prompt = "test"
    image_gen.n = 1
    image_gen.quality = None
    image_gen.size = None
    image_gen.style = None
    image_gen.response_format = None
    image_gen.model = None

    search_space = MagicMock()
    search_space.image_gen_model_id = global_model["id"]
    session = MagicMock()

    with (
        patch.object(
            image_generation_routes,
            "_get_global_model",
            return_value=global_model,
        ),
        patch.object(
            image_generation_routes,
            "_get_global_connection",
            return_value=global_connection,
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

    assert captured.get("api_base") == "https://openrouter.ai/api/v1"
    assert captured["model"] == "openrouter/openai/gpt-image-1"


@pytest.mark.asyncio
async def test_generate_image_tool_global_sets_explicit_api_base():
    """Same explicit-base behavior at the agent tool entry point — both surfaces share
    the same OpenRouter config payloads."""
    from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools import (
        generate_image as gi_module,
    )

    global_model = {
        "id": -20_001,
        "connection_id": -101,
        "model_id": "openai/gpt-image-1",
        "supports_image_generation": True,
        "capabilities_override": {},
    }
    global_connection = {
        "id": -101,
        "provider": "openrouter",
        "api_key": "sk-or-test",
        "base_url": "https://openrouter.ai/api/v1",
        "extra": {},
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
    search_space.image_gen_model_id = global_model["id"]

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
        patch.object(gi_module, "_get_global_model", return_value=global_model),
        patch.object(
            gi_module, "_get_global_connection", return_value=global_connection
        ),
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
        # The live tool takes an injected ToolRuntime and returns a Command;
        # drive the raw coroutine with a minimal runtime (the tool only reads
        # ``tool_call_id``). We assert on what was forwarded to litellm, not
        # on the return value.
        runtime = ToolRuntime(
            state={},
            context=None,
            config={},
            stream_writer=None,
            tool_call_id="call-1",
            store=None,
        )
        await tool.coroutine(prompt="a cat", n=1, runtime=runtime)

    assert captured.get("api_base") == "https://openrouter.ai/api/v1"
    assert captured["model"] == "openrouter/openai/gpt-image-1"


def test_image_gen_router_deployment_sets_explicit_api_base():
    """The Auto-mode router pool carries explicit api_base into deployments."""
    from app.services.image_gen_router_service import ImageGenRouterService

    deployment = ImageGenRouterService._config_to_deployment(
        {
            "model_name": "openai/gpt-image-1",
            "litellm_provider": "openrouter",
            "api_key": "sk-or-test",
            "api_base": "https://openrouter.ai/api/v1",
        }
    )
    assert deployment is not None
    assert deployment["litellm_params"]["api_base"] == "https://openrouter.ai/api/v1"
    assert deployment["litellm_params"]["model"] == "openrouter/openai/gpt-image-1"
