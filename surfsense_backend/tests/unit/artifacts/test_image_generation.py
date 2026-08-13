"""Unit checks for the image-generation seam shared by all three doors."""

from __future__ import annotations

import base64

import pytest

import app.artifacts.generation.image.executor as executor_mod
from app.artifacts.generation.image.executor import run_image_generation
from app.artifacts.generation.image.resolve import (
    ImageModelUnavailableError,
    ResolvedImageModel,
    resolve_anonymous_image_model,
)
from app.artifacts.media.image.bytes import image_bytes_from_response

pytestmark = pytest.mark.unit


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def model_dump(self):
        return {"data": self._data}


async def test_executor_normalizes_provider_relative_urls(monkeypatch):
    async def fake_aimage_generation(*, prompt, model, **kwargs):
        return _FakeResponse([{"url": "/files/abc.png"}])

    monkeypatch.setattr(executor_mod, "aimage_generation", fake_aimage_generation)

    model = ResolvedImageModel(
        model_string="openai/dall-e-3",
        gen_kwargs={},
        provider_base_url="https://prov.example/v1",
    )
    out = await run_image_generation(model, prompt="a cat", n=1)
    assert out["data"][0]["url"] == "https://prov.example/files/abc.png"


async def test_image_bytes_decodes_b64_and_sniffs_type():
    jpeg = b"\xff\xd8\xff\xe0hello"
    response = {"data": [{"b64_json": base64.b64encode(jpeg).decode()}]}
    data, mime, ext = await image_bytes_from_response(response)
    assert data == jpeg
    assert mime == "image/jpeg"
    assert ext == "jpg"


def test_resolve_anonymous_requires_a_flagged_config(monkeypatch):
    from app.artifacts.generation.image import resolve as resolve_mod

    # No flagged config -> unavailable.
    monkeypatch.setattr(resolve_mod.config, "GLOBAL_IMAGE_GEN_CONFIGS", [])
    with pytest.raises(ImageModelUnavailableError):
        resolve_anonymous_image_model()

    # A flagged config resolves to a concrete litellm model string.
    monkeypatch.setattr(
        resolve_mod.config,
        "GLOBAL_IMAGE_GEN_CONFIGS",
        [
            {
                "anonymous_enabled": True,
                "model_name": "dall-e-3",
                "provider": "openai",
                "api_key": "sk-test",
                "seo_slug": "ai-image-generator",
            }
        ],
    )
    resolved = resolve_anonymous_image_model()
    assert resolved.model_string == "openai/dall-e-3"
    assert resolved.config_id is None
