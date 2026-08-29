from __future__ import annotations

import io
import wave
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools import (
    synthesize_narration as narration_tool,
)
from tests.utils.fake_sandbox import FakeSandboxSession

pytestmark = pytest.mark.unit

WORKSPACE_ID = 7


def _runtime():
    return SimpleNamespace(
        tool_call_id="call-1",
        state={},
        config={"configurable": {"thread_id": "41::task:call-1"}},
    )


def _silent_wav(duration_seconds: float = 0.1, sample_rate: int = 8000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"\0\0" * round(duration_seconds * sample_rate))
    return buffer.getvalue()


class _Registry:
    def __init__(self, session: FakeSandboxSession) -> None:
        self.session = session

    async def get_session(self, thread_id, workspace_id):
        assert thread_id == 41
        assert workspace_id == WORKSPACE_ID
        return self.session


def _patch_dependencies(monkeypatch, session: FakeSandboxSession):
    captured: dict = {}
    requests: list[tuple[str, object, str]] = []
    audio = _silent_wav()

    async def get_registry():
        return _Registry(session)

    @asynccontextmanager
    async def db_session():
        yield object()

    async def resolve_billing(_session, workspace_id, *, thread_id=None):
        assert workspace_id == WORKSPACE_ID
        assert thread_id == 41
        return uuid4(), "free", "test-model"

    @asynccontextmanager
    async def billing(**kwargs):
        captured.update(kwargs)
        yield

    async def synthesize(transcript, voice, language):
        requests.append((transcript, voice, language))
        return audio

    async def probe_audio_duration(_session, _path):
        return 0.1

    monkeypatch.setattr(narration_tool, "get_registry", get_registry)
    monkeypatch.setattr(narration_tool, "shielded_async_session", db_session)
    monkeypatch.setattr(
        narration_tool, "_resolve_agent_billing_for_workspace", resolve_billing
    )
    monkeypatch.setattr(narration_tool, "billable_call", billing)
    monkeypatch.setattr(narration_tool, "_synthesize", synthesize)
    monkeypatch.setattr(narration_tool, "_probe_audio_duration", probe_audio_duration)
    monkeypatch.setattr(
        narration_tool,
        "get_text_to_speech",
        lambda: SimpleNamespace(container="wav"),
    )
    monkeypatch.setattr(narration_tool.app_config, "TTS_SERVICE", "local/kokoro")
    monkeypatch.setattr(
        narration_tool.app_config, "VIDEO_PRESENTATION_DEFAULT_LANGUAGE", "en"
    )
    return captured, requests, audio


async def test_tool_writes_audio_only_under_workdir_public_and_returns_filenames(
    monkeypatch,
):
    session = FakeSandboxSession({})
    billing, requests, audio = _patch_dependencies(monkeypatch, session)
    tool = narration_tool.create_synthesize_narration_tool(
        workspace_id=WORKSPACE_ID, db_session=object()
    )

    result = await tool.coroutine(
        slides=[
            {"slide_number": 2, "transcript": "  第二のスライド  "},
            {"slide_number": 1, "transcript": "最初のスライド"},
        ],
        workdir="/workspace/video-render-abc",
        language="ja",
        runtime=_runtime(),
    )

    assert result == [
        {
            "slide_number": 2,
            "audio": "slide-2.wav",
            "duration_seconds": 0.1,
        },
        {
            "slide_number": 1,
            "audio": "slide-1.wav",
            "duration_seconds": 0.1,
        },
    ]
    assert session.writes == {
        "/workspace/video-render-abc/public/slide-2.wav": audio,
        "/workspace/video-render-abc/public/slide-1.wav": audio,
    }
    assert [request[0] for request in requests] == [
        "第二のスライド",
        "最初のスライド",
    ]
    assert all(request[2] == "ja" for request in requests)
    assert all(str(request[1]).startswith("j") for request in requests)
    assert billing["usage_type"] == "video_presentation_generation"
    assert (
        billing["quota_reserve_micros_override"]
        == narration_tool.app_config.QUOTA_DEFAULT_VIDEO_PRESENTATION_RESERVE_MICROS
    )
    assert billing["call_details"] == {
        "thread_id": 41,
        "slide_count": 2,
        "language": "ja",
        "tts_service": "local/kokoro",
    }


async def test_mock_tts_output_is_nonempty_measurable_audio(monkeypatch):
    session = FakeSandboxSession({})
    _patch_dependencies(monkeypatch, session)
    tool = narration_tool.create_synthesize_narration_tool(
        workspace_id=WORKSPACE_ID, db_session=object()
    )

    [result] = await tool.coroutine(
        slides=[{"slide_number": 1, "transcript": "Narration"}],
        workdir="/workspace/video-render-abc",
        language="en",
        runtime=_runtime(),
    )

    data = session.files[f"/workspace/video-render-abc/public/{result['audio']}"]
    assert data
    with wave.open(io.BytesIO(data), "rb") as audio:
        assert audio.getnframes() / audio.getframerate() > 0


@pytest.mark.parametrize(
    ("duration", "rejected"),
    [(180.0, False), (180.000001, True)],
)
async def test_exact_narration_duration_boundary(monkeypatch, duration, rejected):
    session = FakeSandboxSession({})
    _patch_dependencies(monkeypatch, session)

    async def probe_audio_duration(_session, _path):
        return duration

    monkeypatch.setattr(narration_tool, "_probe_audio_duration", probe_audio_duration)
    tool = narration_tool.create_synthesize_narration_tool(
        workspace_id=WORKSPACE_ID, db_session=object()
    )
    call = tool.coroutine(
        slides=[{"slide_number": 1, "transcript": "Narration"}],
        workdir="/workspace/video-render-abc",
        language="en",
        runtime=_runtime(),
    )

    if rejected:
        with pytest.raises(ValueError, match="180-second"):
            await call
    else:
        assert (await call)[0]["duration_seconds"] == 180.0


@pytest.mark.parametrize(
    "workdir",
    [
        "workspace/render",
        "/workspace",
        "/tmp/render",
        "/workspace/render/../../tmp/escape",
    ],
)
async def test_unsafe_workdir_is_rejected_before_tts_or_sandbox_access(
    monkeypatch, workdir
):
    called = False

    async def synthesize(*_args):
        nonlocal called
        called = True
        return b"audio"

    monkeypatch.setattr(narration_tool, "_synthesize", synthesize)
    monkeypatch.setattr(
        narration_tool,
        "get_text_to_speech",
        lambda: SimpleNamespace(container="wav"),
    )
    monkeypatch.setattr(narration_tool.app_config, "TTS_SERVICE", "local/kokoro")
    tool = narration_tool.create_synthesize_narration_tool(
        workspace_id=WORKSPACE_ID, db_session=object()
    )

    with pytest.raises(ValueError, match="workdir"):
        await tool.coroutine(
            slides=[{"slide_number": 1, "transcript": "Narration"}],
            workdir=workdir,
            language="en",
            runtime=_runtime(),
        )

    assert called is False


@pytest.mark.parametrize(
    ("slides", "message"),
    [
        ([], "at least one"),
        ([{"slide_number": 0, "transcript": "x"}], "positive"),
        ([{"slide_number": 1, "transcript": "  "}], "must not be empty"),
        (
            [
                {"slide_number": 1, "transcript": "one"},
                {"slide_number": 1, "transcript": "two"},
            ],
            "duplicate",
        ),
        (
            [
                {"slide_number": number, "transcript": "narration"}
                for number in range(1, 14)
            ],
            "12-scene",
        ),
    ],
)
async def test_invalid_slide_contract_is_rejected(monkeypatch, slides, message):
    monkeypatch.setattr(narration_tool.app_config, "TTS_SERVICE", "local/kokoro")
    tool = narration_tool.create_synthesize_narration_tool(
        workspace_id=WORKSPACE_ID, db_session=object()
    )

    with pytest.raises(ValueError, match=message):
        await tool.coroutine(
            slides=slides,
            workdir="/workspace/video-render-abc",
            language="en",
            runtime=_runtime(),
        )


def test_tool_schema_exposes_only_the_authored_video_contract():
    tool = narration_tool.create_synthesize_narration_tool(
        workspace_id=WORKSPACE_ID, db_session=object()
    )

    assert set(tool.args) == {"slides", "workdir", "language"}
    schema = tool.tool_call_schema.model_json_schema()
    slide_schema = schema["$defs"]["NarrationSlide"]
    assert set(slide_schema["properties"]) == {"slide_number", "transcript"}
    assert set(slide_schema["required"]) == {"slide_number", "transcript"}
    assert tool.metadata["activity_descriptor"]["icon_key"] == "clapperboard"
