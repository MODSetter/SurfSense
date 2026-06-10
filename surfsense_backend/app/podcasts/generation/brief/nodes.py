"""Brief-planning nodes: detect the language, then propose a full spec.

Only ``detect_language`` spends tokens, and only a small sample of source text;
``propose_spec`` is pure resolution. Together they open the brief gate pre-filled
so the common case needs no edits.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.config import config as app_config
from app.podcasts.resolution import (
    DEFAULT_LANGUAGE,
    LanguageContext,
    resolve_language,
    resolve_voices,
)
from app.podcasts.schemas import (
    DurationTarget,
    PodcastSpec,
    PodcastStyle,
    SpeakerRole,
    SpeakerSpec,
    normalize_language_tag,
)
from app.podcasts.voices import (
    VoiceCatalog,
    TtsProvider,
    get_voice_catalog,
    provider_from_service,
)
from app.services.llm_service import get_agent_llm

from ..prompts import detect_language_prompt
from ..structured import StructuredOutputError, invoke_json
from .config import BriefConfig
from .detection import DetectedLanguage
from .state import BriefState

# Only the head of the source is needed to judge language; this caps tokens.
_DETECTION_SAMPLE_CHARS = 4000

# Default role per speaker slot; extra speakers beyond the list fall back to guest.
_ROLE_BY_SLOT = (
    SpeakerRole.HOST,
    SpeakerRole.GUEST,
    SpeakerRole.EXPERT,
    SpeakerRole.COHOST,
    SpeakerRole.NARRATOR,
)


async def detect_language(
    state: BriefState, config: RunnableConfig
) -> dict[str, Any]:
    """Detect the source language; defer (``None``) on any uncertainty."""
    brief = BriefConfig.from_runnable_config(config)
    llm = await get_agent_llm(state.db_session, brief.search_space_id)
    if llm is None:
        return {"detected_language": None}

    sample = (state.source_content or "")[:_DETECTION_SAMPLE_CHARS].strip()
    if not sample:
        return {"detected_language": None}

    messages = [
        SystemMessage(content=detect_language_prompt()),
        HumanMessage(content=f"<source_content>{sample}</source_content>"),
    ]
    try:
        detected = await invoke_json(llm, messages, DetectedLanguage)
    except StructuredOutputError:
        return {"detected_language": None}
    return {"detected_language": detected.language}


def propose_spec(state: BriefState, config: RunnableConfig) -> dict[str, Any]:
    """Build a complete :class:`PodcastSpec` from the resolved defaults."""
    brief = BriefConfig.from_runnable_config(config)
    provider = _active_provider()
    catalog = get_voice_catalog()

    language = _supported_language(
        detected=state.detected_language,
        last_used=brief.last_used_language,
        provider=provider,
        catalog=catalog,
    )
    voices = resolve_voices(
        catalog=catalog,
        provider=provider,
        language=language,
        speaker_count=brief.speaker_count,
        preferred=brief.last_used_voices,
    )

    speakers = [
        SpeakerSpec(
            slot=slot,
            name=_default_name(slot),
            role=_role_for(slot),
            voice_id=voice.voice_id,
        )
        for slot, voice in enumerate(voices)
    ]
    spec = PodcastSpec(
        language=language,
        style=PodcastStyle.CONVERSATIONAL,
        speakers=speakers,
        duration=DurationTarget(
            min_minutes=brief.min_minutes, max_minutes=brief.max_minutes
        ),
        focus=brief.focus,
    )
    return {"spec": spec}


def _active_provider() -> TtsProvider:
    service = app_config.TTS_SERVICE
    if not service:
        raise ValueError("TTS_SERVICE is not configured")
    return provider_from_service(service)


def _supported_language(
    *,
    detected: str | None,
    last_used: str | None,
    provider: TtsProvider,
    catalog: VoiceCatalog,
) -> str:
    raw = resolve_language(LanguageContext(detected=detected, last_used=last_used))
    try:
        language = normalize_language_tag(raw)
    except ValueError:
        language = DEFAULT_LANGUAGE
    if not catalog.supports_language(provider, language):
        return DEFAULT_LANGUAGE
    return language


def _role_for(slot: int) -> SpeakerRole:
    return _ROLE_BY_SLOT[slot] if slot < len(_ROLE_BY_SLOT) else SpeakerRole.GUEST


def _default_name(slot: int) -> str:
    role = _role_for(slot)
    label = role.value.replace("cohost", "co-host").title()
    return label if slot < len(_ROLE_BY_SLOT) else f"{label} {slot}"
