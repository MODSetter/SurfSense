import base64

import pytest

from modules.llm.connections.service import normalize_base_url, parse_models
from modules.llm.providers.openai_compatible.chat import _delta
from modules.llm.providers.openai_compatible.image import (
    NonRetryableImageError,
    OpenAICompatibleImageProvider,
    _route_cache,
)

pytestmark = pytest.mark.unit
PNG = b"\x89PNG\r\n\x1a\nfake"
PAYLOAD = {
    "data": [
        {
            "b64_json": base64.b64encode(PNG).decode(),
            "media_type": "image/png",
        }
    ]
}


def test_base_url_is_normalized_without_weakening_internal_network_support() -> None:
    """Internal HTTP is valid, while credentials and query state are rejected."""
    assert normalize_base_url(" http://127.0.0.1:8000/v1/ ") == (
        "http://127.0.0.1:8000/v1"
    )
    with pytest.raises(ValueError, match="credentials"):
        normalize_base_url("https://user:pass@example.test/v1")
    with pytest.raises(ValueError, match="query"):
        normalize_base_url("https://example.test/v1?token=secret")


def test_capabilities_are_declared_inferred_or_read_as_unknown() -> None:
    """An endpoint that publishes modalities is believed; the rest go by name.

    The bare ids are real: OpenAI and Gemini return nothing else from /models,
    so without the fallback every row lands unclassified and the chat and image
    filters both come back empty over a list 138 long.
    """
    models = {
        model.name: model
        for model in parse_models(
            {
                "data": [
                    {"id": "openai/gpt-4o", "output_modalities": ["text"]},
                    {"id": "gpt-image-2.5-flare"},
                    {"id": "models/gemini-3.1-flash-image"},
                    {"id": "gpt-4o-mini"},
                    {"id": "text-embedding-3-large"},
                ]
            }
        )
    }

    declared = models["openai/gpt-4o"]
    assert declared.capabilities == ("completion",)
    assert declared.capability_source == "declared"
    assert declared.capability_known is True

    for name in ("gpt-image-2.5-flare", "models/gemini-3.1-flash-image"):
        assert models[name].capabilities == ("image_generation",)
        assert models[name].capability_source == "inferred"
        # A guess must stay out of the gate a declaration passes through.
        assert models[name].capability_known is False

    assert models["gpt-4o-mini"].capabilities == ("completion",)
    assert models["text-embedding-3-large"].capability_source == "unknown"


def test_delta_reads_openai_sse_and_ignores_done() -> None:
    """Chat streaming retains the existing OpenAI delta behavior."""
    assert _delta('data: {"choices":[{"delta":{"content":"hi"}}]}') == "hi"
    assert _delta("data: [DONE]") is None


async def test_image_route_falls_back_only_after_missing_standard_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenRouter's /images extension is negotiated once and then cached."""
    _route_cache.clear()
    provider = OpenAICompatibleImageProvider(1, "https://example.test/v1")
    calls: list[str] = []

    async def post(route: str, _model: str, _prompt: str):
        calls.append(route)
        return (404, {}) if route.endswith("generations") else (200, PAYLOAD)

    monkeypatch.setattr(provider, "_post", post)
    first = await provider.generate("image", "draw")
    second = await provider.generate("image", "draw again")

    assert first.content == PNG == second.content
    assert calls == ["/images/generations", "/images", "/images"]


async def test_image_route_does_not_fallback_after_ambiguous_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 5xx may follow billed work, so another image request is forbidden."""
    _route_cache.clear()
    provider = OpenAICompatibleImageProvider(2, "https://example.test/v1")
    calls: list[str] = []

    async def post(route: str, _model: str, _prompt: str):
        calls.append(route)
        return 500, {}

    monkeypatch.setattr(provider, "_post", post)
    with pytest.raises(NonRetryableImageError, match="500"):
        await provider.generate("image", "draw")
    assert calls == ["/images/generations"]
