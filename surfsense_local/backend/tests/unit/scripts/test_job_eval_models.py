"""The job eval's OpenRouter client: a pinned route takes one provider and never falls back, the
reasoning option reaches the request as OpenRouter reads it, and each call's provider is counted."""

import pytest
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
