"""What opencode's request becomes before it reaches the selected model.

opencode names its session in `x-session-affinity` on every request. A remote
endpoint that routes by a conversation key gets it, so an agent's steps reach
the machine that cached their prompt; any other endpoint gets nothing new.
"""

import pytest

from modules.agent.model_endpoint.model_address import ModelAddress
from modules.agent.model_endpoint.request_shaping import shaped_request

pytestmark = pytest.mark.unit

TURN = {
    "model": "surfsense",
    "stream": True,
    "messages": [{"role": "user", "content": "Summarise my sources."}],
}


def _address(url: str, name: str) -> ModelAddress:
    """The selected model at this address, as the endpoint resolves it."""
    return ModelAddress(url, {}, name, ("openai_compatible", name, "1"))


def test_openrouter_keeps_the_agents_session_on_one_provider() -> None:
    """Without it OpenRouter may send the next step to a provider with a cold cache."""
    address = _address(
        "https://openrouter.ai/api/v1/chat/completions", "openai/gpt-5.5"
    )

    body = shaped_request(TURN, address, "ses_42")

    assert body["session_id"] == "ses_42"
    assert body["model"] == "openai/gpt-5.5"


def test_the_local_runtime_gets_no_session_field() -> None:
    """llama-server has one slot, matched by its prefix; a key would route nothing."""
    address = _address("http://127.0.0.1:8080/v1/chat/completions", "Qwen3-8B")

    body = shaped_request(TURN, address, "ses_42")

    assert not {"session_id", "prompt_cache_key"} & body.keys()
