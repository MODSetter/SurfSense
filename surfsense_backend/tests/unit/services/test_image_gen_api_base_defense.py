"""Image-gen call sites must pass each config's explicit ``api_base``."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain.tools import ToolRuntime

pytestmark = pytest.mark.unit


@asynccontextmanager
async def _null_billing(**_kwargs):
    yield


@pytest.mark.asyncio
async def test_generate_image_tool_global_sets_explicit_api_base():
    """The tool forwards the config's explicit OpenRouter base to litellm."""
    from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools import (
        generate_image as gi_module,
    )
    from app.artifacts.media.image import generation as image_generation

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

    workspace = MagicMock()
    workspace.id = 1
    workspace.image_gen_model_id = global_model["id"]

    session_cm = AsyncMock()
    session = AsyncMock()
    session_cm.__aenter__.return_value = session

    scalars = MagicMock()
    scalars.first.return_value = workspace
    exec_result = MagicMock()
    exec_result.scalars.return_value = scalars
    session.execute.return_value = exec_result
    session.commit = AsyncMock()

    async def fake_resolve_billing(*_args, **_kwargs):
        return ("free", "openrouter/openai/gpt-image-1", 50_000)

    async def fake_record(*_args, **_kwargs):
        return SimpleNamespace(artifact_id=7, title="a cat")

    with (
        patch.object(gi_module, "shielded_async_session", return_value=session_cm),
        patch.object(image_generation, "get_global_model", return_value=global_model),
        patch.object(
            image_generation, "get_global_connection", return_value=global_connection
        ),
        patch.object(
            image_generation, "aimage_generation", side_effect=fake_aimage_generation
        ),
        patch.object(
            image_generation,
            "is_image_gen_auto_mode",
            side_effect=lambda cid: cid == 0,
        ),
        patch.object(
            image_generation,
            "resolve_billing_for_image_gen",
            side_effect=fake_resolve_billing,
        ),
        patch.object(image_generation, "billable_call", _null_billing),
        patch.object(gi_module, "record_image", side_effect=fake_record),
        patch.object(gi_module, "resolve_root_thread_id", return_value=None),
    ):
        tool = gi_module.create_generate_image_tool(
            workspace_id=1, db_session=MagicMock()
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
