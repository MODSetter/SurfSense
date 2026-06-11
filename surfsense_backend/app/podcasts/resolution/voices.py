"""Assign a default voice to each speaker for the resolved language.

The default chain reuses the user's previously chosen voices where they are
still valid for the new language/provider, then fills any remaining speakers
with distinct catalog voices (preferring an unused gender so a two-speaker
episode sounds like two people). The user can override any of these in the
brief; this only seeds sensible defaults so most briefs need no edits.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.podcasts.voices import CatalogVoice, TtsProvider, VoiceCatalog


class VoiceResolutionError(RuntimeError):
    """No catalog voice exists for the requested provider and language."""


def resolve_voices(
    *,
    catalog: VoiceCatalog,
    provider: TtsProvider,
    language: str,
    speaker_count: int,
    preferred: Sequence[str] | None = None,
) -> list[CatalogVoice]:
    """Return one :class:`CatalogVoice` per speaker, in slot order.

    ``preferred`` is the user's last-used voice ids (by slot); any that no
    longer fit the provider/language are silently dropped and replaced.
    """
    if speaker_count < 1:
        raise ValueError("speaker_count must be >= 1")

    available = catalog.for_language(provider, language)
    if not available:
        raise VoiceResolutionError(
            f"{provider.value} has no voice for language {language!r}"
        )

    preferred = preferred or ()
    by_id = {voice.voice_id: voice for voice in available}

    assignment: list[CatalogVoice] = []
    used_ids: set[str] = set()
    used_genders: set = set()

    for slot in range(speaker_count):
        reuse_id = preferred[slot] if slot < len(preferred) else None
        if reuse_id and reuse_id in by_id and reuse_id not in used_ids:
            voice = by_id[reuse_id]
        else:
            voice = _pick_distinct(available, used_ids, used_genders)
        assignment.append(voice)
        used_ids.add(voice.voice_id)
        used_genders.add(voice.gender)

    return assignment


def _pick_distinct(
    available: list[CatalogVoice],
    used_ids: set[str],
    used_genders: set,
) -> CatalogVoice:
    """Pick a fresh voice, preferring an unused gender, then any unused voice.

    Falls back to the first catalog voice when speakers outnumber distinct
    voices, so resolution always assigns every speaker rather than failing.
    """
    fresh = [v for v in available if v.voice_id not in used_ids]
    if fresh:
        for voice in fresh:
            if voice.gender not in used_genders:
                return voice
        return fresh[0]
    return available[0]
