"""Trusted-side narration synthesis for sandbox-authored videos."""

from __future__ import annotations

import asyncio
import json
import math
import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TypedDict

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.core import ActivityDescriptor
from app.config import config as app_config
from app.db import shielded_async_session
from app.deliverables.jobs.policy import VIDEO_SPEC
from app.podcasts.resolution import DEFAULT_LANGUAGE, resolve_voices
from app.podcasts.schemas import normalize_language_tag
from app.podcasts.tts import SynthesisRequest, VoiceRef, get_text_to_speech
from app.podcasts.voices import (
    TtsProvider,
    VoiceCatalog,
    get_voice_catalog,
    provider_from_service,
)
from app.sandbox import SandboxSession, get_registry
from app.services.billable_calls import (
    BillingSettlementError,
    QuotaInsufficientError,
    _resolve_agent_billing_for_workspace,
    billable_call,
)

from .thread_resolver import resolve_root_thread_id

_SANDBOX_WORKSPACE = PurePosixPath("/workspace")
_LEGACY_ENGLISH_VOICE_ID: dict[TtsProvider, str] = {
    TtsProvider.KOKORO: "kokoro:af_heart",
    TtsProvider.OPENAI: "openai:alloy",
    TtsProvider.AZURE: "azure:alloy",
    TtsProvider.VERTEX_AI: "vertex_ai:en-US-Studio-O",
}


class NarrationSlide(TypedDict):
    """One numbered narration transcript."""

    slide_number: int
    transcript: str


class NarrationAudio(TypedDict):
    """A sandbox-public audio filename for one slide."""

    slide_number: int
    audio: str
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class _NarrationVoice:
    language: str
    voice: VoiceRef


def _active_provider() -> TtsProvider:
    service = app_config.TTS_SERVICE
    if not service:
        raise ValueError("TTS_SERVICE is not configured")
    return provider_from_service(service)


def _resolve_narration(declared: str | None) -> _NarrationVoice:
    """Lifted language/voice policy from the legacy video graph."""
    provider = _active_provider()
    catalog = get_voice_catalog()
    language = _supported_language(declared, provider=provider, catalog=catalog)
    seed = _LEGACY_ENGLISH_VOICE_ID.get(provider)
    voice = resolve_voices(
        catalog=catalog,
        provider=provider,
        language=language,
        speaker_count=1,
        preferred=[seed] if seed else None,
    )[0].native_ref
    return _NarrationVoice(language=language, voice=voice)


def _supported_language(
    declared: str | None, *, provider: TtsProvider, catalog: VoiceCatalog
) -> str:
    for candidate in (declared, app_config.VIDEO_PRESENTATION_DEFAULT_LANGUAGE):
        if not candidate or not candidate.strip():
            continue
        try:
            language = normalize_language_tag(candidate)
        except ValueError:
            continue
        if catalog.supports_language(provider, language):
            return language
    return DEFAULT_LANGUAGE


async def _synthesize(transcript: str, voice: VoiceRef, language: str) -> bytes:
    """Synthesize one transcript on the trusted side and return inert bytes."""
    audio = await get_text_to_speech().synthesize(
        SynthesisRequest(text=transcript, voice=voice, language=language)
    )
    if not audio.data:
        raise RuntimeError("TTS provider returned empty audio")
    return audio.data


def _public_audio_path(workdir: str, slide_number: int, extension: str) -> str:
    """Build a path confined to ``/workspace/<workdir>/public``."""
    candidate = PurePosixPath(workdir)
    if (
        not candidate.is_absolute()
        or ".." in candidate.parts
        or candidate == _SANDBOX_WORKSPACE
        or not candidate.is_relative_to(_SANDBOX_WORKSPACE)
    ):
        raise ValueError(
            "workdir must be an absolute directory below /workspace without '..'"
        )
    if not extension or not extension.isalnum():
        raise ValueError("TTS provider returned an invalid audio container")
    return str(candidate / "public" / f"slide-{slide_number}.{extension.lower()}")


async def _write_into_public(
    session: SandboxSession,
    workdir: str,
    slide_number: int,
    extension: str,
    audio_bytes: bytes,
) -> str:
    """Write inert audio bytes and return the filename used by ``staticFile``."""
    path = _public_audio_path(workdir, slide_number, extension)
    await session.write_file(path, audio_bytes)
    return PurePosixPath(path).name


async def _probe_audio_duration(session: SandboxSession, path: str) -> float:
    result = await session.run_command(
        "ffprobe -v error -show_entries format=duration -of json -- "
        + shlex.quote(path)
    )
    if not result.ok:
        raise ValueError("Could not determine synthesized narration duration")
    try:
        duration = float(json.loads(result.output)["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Synthesized narration returned invalid duration") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Synthesized narration duration must be positive")
    return duration


def _validated_slides(slides: list[NarrationSlide]) -> list[tuple[int, str]]:
    if not slides:
        raise ValueError("slides must contain at least one narration transcript")
    if len(slides) > VIDEO_SPEC.max_scenes:
        raise ValueError(
            f"slides exceeds the {VIDEO_SPEC.max_scenes}-scene video limit"
        )

    validated: list[tuple[int, str]] = []
    seen: set[int] = set()
    for slide in slides:
        slide_number = slide["slide_number"]
        transcript = slide["transcript"]
        if isinstance(slide_number, bool) or not isinstance(slide_number, int):
            raise ValueError("slide_number must be an integer")
        if slide_number < 1:
            raise ValueError("slide_number must be positive")
        if slide_number in seen:
            raise ValueError(f"duplicate slide_number: {slide_number}")
        if not isinstance(transcript, str) or not transcript.strip():
            raise ValueError(f"slide {slide_number} transcript must not be empty")
        seen.add(slide_number)
        validated.append((slide_number, transcript.strip()))
    return validated


async def synthesize_narration(
    slides: list[NarrationSlide],
    workdir: str,
    *,
    workspace_id: int,
    thread_id: int,
    session: SandboxSession,
    language: str | None = None,
) -> list[NarrationAudio]:
    """Synthesize, bill, persist, and measure narration for one video."""
    validated = _validated_slides(slides)
    narration = _resolve_narration(language)
    tts = get_text_to_speech()
    extension = tts.container
    # Validate the destination before making any paid provider calls.
    for slide_number, _ in validated:
        _public_audio_path(workdir, slide_number, extension)

    async with shielded_async_session() as billing_session:
        owner_id, billing_tier, base_model = await _resolve_agent_billing_for_workspace(
            billing_session,
            workspace_id,
            thread_id=thread_id,
        )

    try:
        async with billable_call(
            user_id=owner_id,
            workspace_id=workspace_id,
            billing_tier=billing_tier,
            base_model=base_model,
            quota_reserve_micros_override=(
                app_config.QUOTA_DEFAULT_VIDEO_PRESENTATION_RESERVE_MICROS
            ),
            usage_type="video_presentation_generation",
            call_details={
                "thread_id": thread_id,
                "slide_count": len(validated),
                "language": narration.language,
                "tts_service": app_config.TTS_SERVICE,
            },
        ):
            audio_by_slide = await asyncio.gather(
                *(
                    _synthesize(transcript, narration.voice, narration.language)
                    for _, transcript in validated
                )
            )
    except QuotaInsufficientError:
        raise RuntimeError("Out of credits for premium video generation.") from None
    except BillingSettlementError:
        raise RuntimeError("Video generation billing settlement failed.") from None

    paths = [
        _public_audio_path(workdir, slide_number, extension)
        for slide_number, _ in validated
    ]
    filenames = await asyncio.gather(
        *(
            _write_into_public(
                session,
                workdir,
                slide_number,
                extension,
                audio_bytes,
            )
            for (slide_number, _), audio_bytes in zip(
                validated, audio_by_slide, strict=True
            )
        )
    )
    durations = await asyncio.gather(
        *(_probe_audio_duration(session, path) for path in paths)
    )
    total_duration = sum(durations)
    if total_duration > VIDEO_SPEC.max_duration_seconds:
        raise ValueError(
            "Narration duration exceeds the "
            f"{VIDEO_SPEC.max_duration_seconds}-second video limit"
        )
    return [
        {
            "slide_number": slide_number,
            "audio": filename,
            "duration_seconds": duration,
        }
        for (slide_number, _), filename, duration in zip(
            validated, filenames, durations, strict=True
        )
    ]


def create_synthesize_narration_tool(
    *,
    workspace_id: int,
    db_session: AsyncSession,
) -> BaseTool:
    """Create the narration bridge with its workspace dependency bound."""
    del db_session  # DB and billing work use isolated per-call sessions.

    @tool
    async def synthesize_narration_tool(
        slides: list[NarrationSlide],
        workdir: str,
        runtime: ToolRuntime,
        language: str | None = None,
    ) -> list[NarrationAudio]:
        """Generate narration audio for sandbox-authored video slides.

        ``workdir`` must be the copied Remotion harness directory below
        ``/workspace``. Audio is written only to its ``public/`` directory.
        The returned filenames are suitable for Remotion ``staticFile()``.
        """
        # Preserve trust-boundary validation before resolving sandbox/provider state.
        for slide_number, _ in _validated_slides(slides):
            _public_audio_path(workdir, slide_number, "wav")
        thread_id = resolve_root_thread_id(runtime)
        session = await (await get_registry()).get_session(thread_id, workspace_id)
        return await synthesize_narration(
            slides,
            workdir,
            workspace_id=workspace_id,
            thread_id=thread_id,
            session=session,
            language=language,
        )

    synthesize_narration_tool.name = "synthesize_narration"
    synthesize_narration_tool.metadata = {
        "activity_descriptor": ActivityDescriptor(
            active_title="Narrating the video",
            completed_title="Narrated the video",
            category="action",
            icon_key="clapperboard",
            kind="synthesize_narration",
        ).as_metadata()
    }
    return synthesize_narration_tool
