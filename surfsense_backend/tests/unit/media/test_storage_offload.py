"""Unit checks for image/video object-store offload helpers."""

from __future__ import annotations

import base64

import pytest

from app.artifacts.media.image.storage import offload_b64
from app.artifacts.media.video.storage import offload_slide_audio


@pytest.mark.asyncio
async def test_offload_b64_strips_b64_and_sets_storage_key(monkeypatch):
    stored: dict[str, bytes] = {}

    class FakeBackend:
        backend_name = "local"

        async def put(self, key, data, *, content_type=None):
            stored[key] = data

        def open_stream(self, key):
            async def gen():
                yield stored[key]

            return gen()

        async def delete(self, key):
            stored.pop(key, None)

        async def exists(self, key):
            return key in stored

    monkeypatch.setattr(
        "app.artifacts.media.image.storage.get_storage_backend",
        lambda: FakeBackend(),
    )

    raw = b"\x89PNG-test"
    payload = {
        "data": [
            {"b64_json": base64.b64encode(raw).decode("ascii"), "url": None},
            {"url": "https://cdn.example/a.png"},
        ]
    }
    result = await offload_b64(payload, workspace_id=1, image_gen_id=9)
    first, second = result["data"]
    assert "b64_json" not in first
    assert first["storage_key"].startswith("images/1/9/")
    assert stored[first["storage_key"]] == raw
    assert second.get("url") == "https://cdn.example/a.png"
    assert "storage_key" not in second


@pytest.mark.asyncio
async def test_offload_slide_audio_uploads_and_drops_local_path(monkeypatch, tmp_path):
    stored: dict[str, bytes] = {}

    class FakeBackend:
        backend_name = "local"

        async def put(self, key, data, *, content_type=None):
            stored[key] = data

        def open_stream(self, key):
            async def gen():
                yield stored[key]

            return gen()

        async def delete(self, key):
            stored.pop(key, None)

        async def exists(self, key):
            return key in stored

    monkeypatch.setattr(
        "app.artifacts.media.video.storage.get_storage_backend",
        lambda: FakeBackend(),
    )

    audio_path = tmp_path / "slide1.mp3"
    audio_path.write_bytes(b"ID3audio")
    slides = [
        {
            "slide_number": 1,
            "audio_file": str(audio_path),
            "duration_seconds": 1.0,
        }
    ]
    result = await offload_slide_audio(
        slides, workspace_id=2, video_presentation_id=5
    )
    assert "audio_file" not in result[0]
    assert result[0]["audio_storage_key"].startswith("video_presentations/2/5/")
    assert stored[result[0]["audio_storage_key"]] == b"ID3audio"
    assert not audio_path.exists()
