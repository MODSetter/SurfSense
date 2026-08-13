"""Media record helpers: image delivers straight to an Artifact, podcast and
video still carry legacy metadata until their own row is reshaped."""

from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest

import app.artifacts.media.image.record as image_record_mod
import app.artifacts.media.podcast.record as podcast_record_mod
from app.artifacts.media.naming import primary_filename
from app.artifacts.media.podcast.record import _to_artifact_input as podcast_input
from app.artifacts.media.video.record import _to_artifact_input as video_input
from app.artifacts.persistence import ArtifactFileRole, ArtifactFormat
from app.artifacts.schemas import ArtifactFileInput, ArtifactSaved, ArtifactSavedFile
from app.artifacts.service import _artifact_format, _validated_files


def test_primary_filename_sanitizes_and_forces_extension():
    assert primary_filename("Weekly brief", extension="mp3", fallback="podcast") == (
        "Weekly brief.mp3"
    )
    evil = primary_filename("../evil/name", extension="png", fallback="image")
    assert evil.endswith(".png")
    assert "/" not in evil
    assert "\\" not in evil
    assert ".." not in evil
    assert primary_filename("  ", extension="mp3", fallback="podcast") == "podcast.mp3"
    assert primary_filename(
        "foo.bar baz", extension="mp3", fallback="podcast"
    ).endswith(".mp3")
    messy = primary_filename("a/b\\c:d", extension="mp3", fallback="x")
    assert "/" not in messy and "\\" not in messy and ":" not in messy
    assert messy.endswith(".mp3")


def test_podcast_input_sets_format_and_legacy_via_record_helper():
    payload = podcast_input(
        workspace_id=1,
        podcast_id=42,
        title="Weekly brief",
        markdown_representation="# Weekly brief\n\nTranscript…",
        audio=b"ID3fake",
        thread_id=7,
        artifact_id=None,
        expected_generation=None,
    )
    assert payload.format is ArtifactFormat.PODCAST
    assert payload.metadata["legacy"] == {"kind": "podcast", "id": 42}
    assert payload.files[0].filename == "Weekly brief.mp3"
    assert payload.files[0].role is ArtifactFileRole.PRIMARY
    assert payload.files[0].mime_type == "audio/mpeg"


def test_video_input_sets_explicit_format():
    video = video_input(
        workspace_id=1,
        title="Deck",
        markdown_representation="# Deck",
        narration_audio=b"\xff\xfb",
        thread_id=None,
        metadata={"legacy": {"kind": "video", "id": 9}},
        artifact_id=None,
        expected_generation=None,
    )
    assert video.format is ArtifactFormat.VIDEO
    assert video.files[0].filename == "Deck.mp3"
    assert isinstance(video.files[0], ArtifactFileInput)


def test_image_type_follows_the_bytes_not_the_request():
    assert image_record_mod._image_type(b"\x89PNG\r\n") == ("png", "image/png")
    assert image_record_mod._image_type(b"\xff\xd8\xff\xe0") == ("jpg", "image/jpeg")
    assert image_record_mod._image_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == (
        "webp",
        "image/webp",
    )


def test_explicit_format_beats_filename_extension():
    files = _validated_files(
        [ArtifactFileInput(b"x", "clip.mp3", "audio/mpeg", ArtifactFileRole.PRIMARY)]
    )
    assert _artifact_format(files) == "mp3"
    assert _artifact_format(files, explicit=ArtifactFormat.PODCAST) == "podcast"


@pytest.mark.asyncio
async def test_record_image_delivers_artifact_with_provenance(monkeypatch):
    captured = {}

    async def fake_save(session, **kwargs):
        captured.update(kwargs)
        return ArtifactSaved(
            status="saved",
            artifact_id=5,
            generation=1,
            title=kwargs["title"],
            files=[],
        )

    monkeypatch.setattr(image_record_mod, "save_artifact", fake_save)

    saved = await image_record_mod.record(
        SimpleNamespace(),
        workspace_id=1,
        prompt="a sunset",
        response={
            "data": [
                {
                    "b64_json": base64.b64encode(b"\x89PNG\r\n").decode(),
                    "revised_prompt": "a vivid sunset",
                }
            ]
        },
        provenance={"model": "gpt-image-1", "n": 1},
        thread_id=7,
        tool_call_id="call-1",
    )

    assert saved.artifact_id == 5
    assert captured["format"] is ArtifactFormat.IMAGE
    assert captured["files"][0].filename == "a sunset.png"
    assert captured["files"][0].mime_type == "image/png"
    assert captured["files"][0].data == b"\x89PNG\r\n"
    assert captured["extra_metadata"] == {
        "model": "gpt-image-1",
        "n": 1,
        "prompt": "a sunset",
        "revised_prompt": "a vivid sunset",
    }
    assert captured["thread_id"] == 7
    assert captured["tool_call_id"] == "call-1"


@pytest.mark.asyncio
async def test_record_image_rejects_a_response_with_no_image(monkeypatch):
    monkeypatch.setattr(image_record_mod, "save_artifact", None)
    with pytest.raises(ValueError):
        await image_record_mod.record(
            SimpleNamespace(),
            workspace_id=1,
            prompt="a sunset",
            response={"data": []},
        )


@pytest.mark.asyncio
async def test_record_podcast_builds_legacy_metadata(monkeypatch):
    captured = {}

    async def fake_persist(session, payload):
        captured["payload"] = payload
        return ArtifactSaved(
            status="saved",
            artifact_id=11,
            generation=1,
            title=payload.title,
            files=[
                ArtifactSavedFile(
                    file_id=1,
                    role=ArtifactFileRole.PRIMARY.value,
                    filename="podcast.mp3",
                    mime_type="audio/mpeg",
                    size_bytes=4,
                )
            ],
        )

    async def no_existing(*_args, **_kwargs):
        return None

    monkeypatch.setattr(podcast_record_mod, "persist_artifact", fake_persist)
    monkeypatch.setattr(podcast_record_mod, "existing_legacy_artifact", no_existing)

    podcast = SimpleNamespace(
        id=42,
        workspace_id=1,
        title="Ep",
        thread_id=7,
    )
    saved = await podcast_record_mod.record(
        SimpleNamespace(),
        podcast,
        audio=b"ID3x",
        transcript=None,
    )
    assert saved is not None
    assert saved.artifact_id == 11
    assert captured["payload"].format is ArtifactFormat.PODCAST
    assert captured["payload"].metadata["legacy"] == {"kind": "podcast", "id": 42}
    assert captured["payload"].files[0].filename == "Ep.mp3"
    assert captured["payload"].tool_call_id is None
