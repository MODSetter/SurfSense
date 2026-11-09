"""The job eval's models: a Claude model with no list price and an OpenRouter pin with no
provider are refused before any call; on OpenRouter a pinned route takes one provider and never
falls back, the reasoning option reaches the request as OpenRouter reads it, each call's provider
is counted, and a rate limit's Retry-After is waited out within a minute."""

import httpx
import pytest
from job_eval import models
from job_eval.models import model_for

pytestmark = pytest.mark.unit


def _sent(monkeypatch, spec: str, reasoning: str = "off", provider: str = "Anthropic"):
    """The request body the client sends for one call, and the model that sent it."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "not-a-key")
    model = model_for(spec, concurrency=1, effort="low", reasoning=reasoning)
    bodies: list[dict] = []

    def post(body: dict) -> dict:
        bodies.append(body)
        return {
            "provider": provider,
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.001},
            "choices": [{"message": {"content": '{"ok": true}'}}],
        }

    model._post = post
    reply = model.ask("system", [("user", "question")], {"type": "object"}, 0)
    assert reply.text == '{"ok": true}'
    return bodies[0], model


def test_a_pinned_model_takes_one_provider_and_never_falls_back(monkeypatch):
    """The pin names the one provider, and the run counts who served the call."""
    body, model = _sent(monkeypatch, "openrouter:anthropic/claude-sonnet-5.5@anthropic")

    assert body["model"] == "anthropic/claude-sonnet-5.5"
    assert body["provider"] == {
        "require_parameters": True,
        "only": ["anthropic"],
        "allow_fallbacks": False,
    }
    assert dict(model.spend.providers) == {"Anthropic": 1}


def test_an_unpinned_model_lets_openrouter_route(monkeypatch):
    """Without a pin only the schema is required of a provider, as for the open models."""
    body, _ = _sent(monkeypatch, "openrouter:google/gemma-4-31b-it", provider="Novita")

    assert body["model"] == "google/gemma-4-31b-it"
    assert body["provider"] == {"require_parameters": True}


@pytest.mark.parametrize(
    ("reasoning", "sent"),
    [
        ("low", {"effort": "low"}),
        ("off", {"enabled": False}),
        ("on", {"enabled": True}),
        ("default", None),
    ],
)
def test_the_reasoning_option_reaches_the_request(monkeypatch, reasoning, sent):
    """Low effort for a model whose reasoning cannot be turned off; nothing for the default."""
    body, _ = _sent(monkeypatch, "openrouter:qwen/qwen3.8-27b", reasoning=reasoning)

    assert body.get("reasoning") == sent


def test_a_claude_model_with_no_list_price_is_refused(monkeypatch):
    """Its calls would be billed but recorded as $0, so the run stops before the first."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-key")

    with pytest.raises(SystemExit):
        model_for(
            "anthropic:claude-sonnet-5", concurrency=1, effort="low", reasoning="off"
        )


def test_a_pin_with_no_provider_is_refused(monkeypatch):
    """A trailing @ would run unpinned, on whichever providers OpenRouter picks."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "not-a-key")

    with pytest.raises(SystemExit):
        model_for(
            "openrouter:qwen/qwen3.8-27b@", concurrency=1, effort="low", reasoning="off"
        )


@pytest.mark.parametrize(
    ("headers", "paused"),
    [
        ({"retry-after": "7"}, 7),
        ({}, 2),
        ({"retry-after": "3600"}, 60),
        ({"retry-after": "-3"}, 2),
    ],
)
def test_a_rate_limit_is_waited_out_as_the_provider_asks(monkeypatch, headers, paused):
    """Retry-After is followed up to a minute, as the app's job run follows it; without a
    usable one the pause is the usual first one."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "not-a-key")
    model = model_for(
        "openrouter:qwen/qwen3.8-27b", concurrency=1, effort="low", reasoning="off"
    )
    replies = iter(
        [
            httpx.Response(429, headers=headers),
            httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]}),
        ]
    )
    monkeypatch.setattr(model._client, "post", lambda url, json: next(replies))
    sleeps: list[float] = []
    monkeypatch.setattr(models.time, "sleep", sleeps.append)

    reply = model.ask("system", [("user", "question")], {"type": "object"}, 0)

    assert reply.text == "{}"
    assert sleeps == [paused]
