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


def test_model_metadata_is_progressive_and_unknown_is_kept() -> None:
    """Rich endpoints expose roles; standard OpenAI rows remain selectable."""
    models = parse_models(
        {
            "data": [
                {"id": "unknown"},
                {"id": "image", "output_modalities": ["image"]},
            ]
        }
    )
    assert models[0].capability_known is False
    assert models[1].capabilities == ("image_generation",)


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
