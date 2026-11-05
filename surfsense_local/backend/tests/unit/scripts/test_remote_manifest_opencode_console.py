"""What OpenCode's docs say about its Console reaches the manifest.

https://opencode.ai/v2/docs/console/harnesses
"""

import pytest
from remote_manifest.translate import translate

from modules.llm.catalog.remote.manifest.loader import (
    load_remote_manifest,
    remote_lookup,
)
from modules.llm.catalog.remote.manifest.lookup import call_reason
from modules.llm.catalog.remote.manifest.schema import Call

pytestmark = pytest.mark.unit


def _console_provider(models: dict) -> dict:
    return {
        "name": "OpenCode",
        "api": "https://opencode.ai/inference/openai/v1",
        "npm": "@ai-sdk/openai-compatible",
        "models": models,
    }


def _anthropic_model(cost: dict) -> dict:
    return {
        "id": "claude-opus-5-5",
        "cost": cost,
        "provider": {"npm": "@ai-sdk/anthropic"},
    }


@pytest.mark.parametrize("provider", ["opencode", "opencode-go"])
def test_a_paid_model_with_another_native_api_is_callable_on_chat_completions(
    provider: str,
) -> None:
    """The docs: "Every API serves every paid and Go text model"."""
    api = {
        provider: _console_provider(
            {"claude": _anthropic_model({"input": 5, "output": 25})}
        )
    }

    model = translate(api)["providers"][provider]["models"]["claude"]

    assert model["call"] is None


@pytest.mark.parametrize("provider", ["opencode", "opencode-go"])
def test_a_free_model_says_it_only_works_inside_opencode(provider: str) -> None:
    """The docs: other harnesses receive a 403. Price decides, since `big-pickle`
    costs nothing and has no `-free` in its name."""
    api = {
        provider: _console_provider(
            {"big-pickle": {"id": "big-pickle", "cost": {"input": 0, "output": 0}}}
        )
    }

    call = translate(api)["providers"][provider]["models"]["big-pickle"]["call"]

    assert (
        call_reason(Call(**call))
        == "OpenCode allows this free model only inside OpenCode"
    )


def test_another_provider_keeps_its_native_protocol() -> None:
    """Only OpenCode's docs promise translation."""
    api = {
        "elsewhere": _console_provider(
            {"claude": _anthropic_model({"input": 5, "output": 25})}
        )
    }

    model = translate(api)["providers"]["elsewhere"]["models"]["claude"]

    assert model["call"] == {"protocol": "anthropic"}


@pytest.mark.parametrize(
    ("provider", "base_url", "paid", "free"),
    [
        (
            "opencode",
            "https://opencode.ai/inference/openai/v1",
            "claude-opus-5-5",
            "big-pickle",
        ),
        (
            "opencode-go",
            "https://opencode.ai/inference/go/openai/v1",
            "claude-haiku-5-5",
            "beam-free",
        ),
    ],
)
def test_the_shipped_manifest_reaches_opencode_as_its_docs_say(
    provider: str, base_url: str, paid: str, free: str
) -> None:
    """The committed file holds the rules, not only the translator."""
    served = load_remote_manifest().providers[provider]
    lookup = remote_lookup()

    assert served.connect.base_url == base_url
    assert lookup.unusable_reason(paid, provider) is None
    assert lookup.unusable_reason(free, provider) is not None
