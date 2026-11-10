import base64

import pytest

from modules.llm.connections.service import normalize_base_url, parse_models
from modules.llm.model_type import ModelType
from modules.llm.providers.openai_compatible import image_response
from modules.llm.providers.openai_compatible.chat import _delta
from modules.llm.providers.openai_compatible.image import (
    NonRetryableImageError,
    OpenAICompatibleImageProvider,
    _asks_for_picture,
    _route_cache,
)
from modules.llm.providers.protocols import GeneratedImage
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


def test_an_endpoints_own_word_for_speech_is_the_audio_slot() -> None:
    """OpenRouter declares `speech` for text-to-speech and `transcription` for
    speech-to-text; each output a model declares is a type, as with images."""
    models = {
        model.name: model
        for model in parse_models(
            {
                "data": [
                    {"id": "omni", "output_modalities": ["text", "audio"]},
                    {
                        "id": "hexgrad/kokoro-82m",
                        "architecture": {"output_modalities": ["speech"]},
                    },
                    {
                        "id": "openai/whisper-1",
                        "architecture": {"output_modalities": ["transcription"]},
                    },
                ]
            }
        )
    }

    assert models["omni"].types == (ModelType.TEXT_GEN, ModelType.AUDIO_GEN)
    assert models["hexgrad/kokoro-82m"].types == (ModelType.AUDIO_GEN,)
    assert models["openai/whisper-1"].types == ()
    assert models["openai/whisper-1"].capability_known is True


def test_an_image_model_that_declares_pictures_in_can_edit() -> None:
    """OpenRouter lists what a model takes as well as what it returns; a picture in
    and a picture out is what an edit, or a comic page's reference, needs."""
    models = {
        model.name: model
        for model in parse_models(
            {
                "data": [
                    {
                        "id": "openai/gpt-image-2.6-flare",
                        "architecture": {
                            "input_modalities": ["text", "image"],
                            "output_modalities": ["image"],
                        },
                    },
                    {
                        "id": "recraft/recraft-v4.1-flash",
                        "architecture": {
                            "input_modalities": ["text"],
                            "output_modalities": ["image"],
                        },
                    },
                    {
                        "id": "openai/gpt-4o",
                        "architecture": {
                            "input_modalities": ["text", "image"],
                            "output_modalities": ["text"],
                        },
                    },
                ]
            }
        )
    }

    assert models["openai/gpt-image-2.6-flare"].types == (
        ModelType.IMAGE_GEN,
        ModelType.IMAGE_EDIT,
    )
    assert models["recraft/recraft-v4.1-flash"].types == (ModelType.IMAGE_GEN,)
    # Reading pictures is not editing them: a chat model stays a chat model.
    assert models["openai/gpt-4o"].types == (ModelType.TEXT_GEN,)


def test_delta_reads_openai_sse_and_ignores_done() -> None:
    """Chat streaming retains the existing OpenAI delta behavior."""
    assert _delta('data: {"choices":[{"delta":{"content":"hi"}}]}') == Delta("hi")
    assert _delta("data: [DONE]") is None


def _provider(connection_id: int) -> OpenAICompatibleImageProvider:
    return OpenAICompatibleImageProvider(connection_id, "https://example.test/v1")


async def test_image_route_falls_back_only_after_missing_standard_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenRouter's /images extension is negotiated once and then cached."""
    _route_cache.clear()
    provider = _provider(1)
    calls: list[str] = []

    async def post(route: str, _model: str, _prompt: str, _picture: bool):
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
    provider = _provider(2)
    calls: list[str] = []

    async def post(route: str, _model: str, _prompt: str, _picture: bool):
        calls.append(route)
        return 500, {}

    monkeypatch.setattr(provider, "_post", post)
    with pytest.raises(NonRetryableImageError, match="500"):
        await provider.generate("image", "draw")
    assert calls == ["/images/generations"]


async def test_the_picture_itself_is_asked_for_rather_than_a_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A link would mean a second request, to a host the provider picks."""
    _route_cache.clear()
    _asks_for_picture.clear()
    provider = _provider(4)
    asked: list[bool] = []

    async def post(_route: str, _model: str, _prompt: str, picture: bool):
        asked.append(picture)
        return 200, PAYLOAD

    monkeypatch.setattr(provider, "_post", post)
    await provider.generate("dall-e-3", "draw")

    assert asked == [True]


async def test_a_model_that_refuses_the_setting_is_asked_again_without_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GPT image models always answer with the picture and refuse the setting;
    a 400 is a refusal before any work, so asking again bills nothing twice."""
    _route_cache.clear()
    _asks_for_picture.clear()
    provider = _provider(5)
    asked: list[bool] = []

    async def post(_route: str, _model: str, _prompt: str, picture: bool):
        asked.append(picture)
        return (400, {}) if picture else (200, PAYLOAD)

    monkeypatch.setattr(provider, "_post", post)
    first = await provider.generate("gpt-image-1", "draw")
    await provider.generate("gpt-image-1", "draw again")

    assert first.content == PNG
    # Remembered: the next image does not ask with the setting first.
    assert asked == [True, False, False]


async def test_a_link_the_model_returns_is_downloaded_without_asking_egress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The user allowed this provider; the link is where it put their picture,
    often on another site, as DALL-E's on Azure storage."""
    _route_cache.clear()
    fetched: list[str] = []

    async def post(_route: str, _model: str, _prompt: str, _picture: bool):
        link = "https://oaidalleapiprodscus.blob.core.windows.net/private/x.png"
        return 200, {"data": [{"url": link}]}

    async def download(url: str) -> GeneratedImage:
        fetched.append(url)
        return GeneratedImage(PNG, "image/png")

    provider = _provider(3)
    monkeypatch.setattr(provider, "_post", post)
    monkeypatch.setattr(image_response, "download_image", download)

    image = await provider.generate("dall-e-3", "draw")

    assert image.content == PNG
    assert fetched == [
        "https://oaidalleapiprodscus.blob.core.windows.net/private/x.png"
    ]


async def test_a_shape_is_asked_for_as_a_size_and_dropped_where_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A comic page is portrait. A server that refuses the size draws its own,
    and a 400 is a refusal before any work, so asking again bills nothing."""
    _route_cache.clear()
    _asks_for_picture.clear()
    provider = _provider(6)
    sizes: list[str | None] = []

    async def post(_route, _model, _prompt, _picture, size=None):
        sizes.append(size)
        return (400, {}) if size else (200, PAYLOAD)

    monkeypatch.setattr(provider, "_post", post)
    await provider.generate("flux", "page one", shape="portrait")
    await provider.generate("flux", "page two", shape="portrait")

    # Without the size, after the picture setting was tried without first.
    assert sizes == ["1024x1536", "1024x1536", None, None]


async def test_a_shape_reaches_a_server_that_takes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only asked for when a picture names a shape."""
    _route_cache.clear()
    _asks_for_picture.clear()
    provider = _provider(7)
    sizes: list[str | None] = []

    async def post(_route, _model, _prompt, _picture, size=None):
        sizes.append(size)
        return 200, PAYLOAD

    monkeypatch.setattr(provider, "_post", post)
    await provider.generate("gpt-image-1", "a strip", shape="landscape")
    await provider.generate("gpt-image-1", "a picture")

    assert sizes == ["1536x1024", None]
