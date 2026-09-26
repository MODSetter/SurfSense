import base64

import pytest

from modules.llm.connections.service import normalize_base_url, parse_models
from modules.llm.model_type import ModelType
from modules.llm.providers.openai_compatible.chat import _delta
from modules.llm.providers.openai_compatible.image import (
    NonRetryableImageError,
    OpenAICompatibleImageProvider,
    _route_cache,
)
from modules.llm.providers.types import Delta

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


def test_types_come_from_the_endpoint_then_the_catalogue_then_nowhere() -> None:
    """Declared beats catalogued beats unknown, and nothing is read off a name.

    The bare ids are real: OpenAI and Gemini return nothing else from /models.
    Every one of them is answered by the reviewed table or not at all, so a row
    the app has never heard of says so instead of being assumed to chat.
    """
    models = {
        model.name: model
        for model in parse_models(
            {
                "data": [
                    {"id": "openai/gpt-4o", "output_modalities": ["text"]},
                    {"id": "gpt-image-2"},
                    {"id": "models/gemini-3.1-flash-image"},
                    {"id": "gpt-4o-mini"},
                    {"id": "whisper-large-v3"},
                    {"id": "veo-3.1-generate-preview"},
                    {"id": "babbage-002"},
                    {"id": "a-model-nobody-has-catalogued"},
                ]
            }
        )
    }

    declared = models["openai/gpt-4o"]
    assert declared.types == (ModelType.TEXT_GEN,)
    assert declared.capability_source == "declared"
    assert declared.capability_known is True

    assert models["gpt-image-2"].types == (ModelType.IMAGE_GEN, ModelType.IMAGE_EDIT)
    assert models["gpt-image-2"].capability_source == "catalog"

    # Resolved by the last path segment, for the ids Gemini and gateways prefix.
    # Several types at once is a real answer, not a conflict: this model returns
    # text alongside the image, and dropping either would hide it from a picker.
    gemini = models["models/gemini-3.1-flash-image"]
    assert gemini.types == (
        ModelType.TEXT_GEN,
        ModelType.IMAGE_GEN,
        ModelType.IMAGE_EDIT,
    )
    assert gemini.capability_source == "catalog"

    assert models["gpt-4o-mini"].types == (ModelType.TEXT_GEN,)
    assert models["gpt-4o-mini"].capability_source == "catalog"

    # Knowing a model is none of the types is an answer, and it is what keeps
    # a transcriber out of every picker.
    assert models["whisper-large-v3"].types == ()
    assert models["whisper-large-v3"].capability_source == "catalog"
    assert models["whisper-large-v3"].capability_known is True

    # The manifest keeps the modalities, so a video model is one, not "neither".
    assert models["veo-3.1-generate-preview"].types == (ModelType.VIDEO_GEN,)

    # Absent from models.dev, so unknown rather than guessed. This is the model
    # that used to be labelled a chat model by reading its name.
    for name in ("babbage-002", "a-model-nobody-has-catalogued"):
        assert models[name].types == ()
        assert models[name].capability_source == "unknown"
        # Unknown must not gate a choice; the test dialog resolves it instead.
        assert models[name].capability_known is False


def test_delta_reads_openai_sse_and_ignores_done() -> None:
    """Chat streaming retains the existing OpenAI delta behavior."""
    assert _delta('data: {"choices":[{"delta":{"content":"hi"}}]}') == Delta("hi")
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
