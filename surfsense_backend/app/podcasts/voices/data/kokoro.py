"""Curated Kokoro voices, the local provider's multilingual roster.

Kokoro voice names encode language and gender in their first two letters
(``a``=American English, ``b``=British, ``e``=Spanish, ``f``=French,
``h``=Hindi, ``i``=Italian, ``j``=Japanese, ``p``=Brazilian Portuguese,
``z``=Mandarin; second letter ``f``/``m`` = female/male). We carry at least one
male and one female voice per language so a two-speaker brief always has a
distinct pair. ``native_ref`` is the bare voice name Kokoro expects.

Reference: https://huggingface.co/hexgrad/Kokoro-82M/tree/main/voices
"""

from __future__ import annotations

from ..provider import TtsProvider
from ..voice import CatalogVoice, VoiceGender


def _voice(name: str, language: str, display: str, gender: VoiceGender) -> CatalogVoice:
    return CatalogVoice(
        voice_id=f"kokoro:{name}",
        provider=TtsProvider.KOKORO,
        language=language,
        display_name=display,
        gender=gender,
        native_ref=name,
    )


KOKORO_VOICES: tuple[CatalogVoice, ...] = (
    # American English
    _voice("am_adam", "en-US", "Adam (US)", VoiceGender.MALE),
    _voice("am_michael", "en-US", "Michael (US)", VoiceGender.MALE),
    _voice("af_bella", "en-US", "Bella (US)", VoiceGender.FEMALE),
    _voice("af_heart", "en-US", "Heart (US)", VoiceGender.FEMALE),
    _voice("af_nicole", "en-US", "Nicole (US)", VoiceGender.FEMALE),
    _voice("af_sarah", "en-US", "Sarah (US)", VoiceGender.FEMALE),
    # British English
    _voice("bm_george", "en-GB", "George (UK)", VoiceGender.MALE),
    _voice("bm_lewis", "en-GB", "Lewis (UK)", VoiceGender.MALE),
    _voice("bf_emma", "en-GB", "Emma (UK)", VoiceGender.FEMALE),
    _voice("bf_isabella", "en-GB", "Isabella (UK)", VoiceGender.FEMALE),
    # Spanish
    _voice("em_alex", "es", "Alex (ES)", VoiceGender.MALE),
    _voice("ef_dora", "es", "Dora (ES)", VoiceGender.FEMALE),
    # French
    _voice("ff_siwis", "fr", "Siwis (FR)", VoiceGender.FEMALE),
    # Hindi
    _voice("hm_omega", "hi", "Omega (HI)", VoiceGender.MALE),
    _voice("hf_alpha", "hi", "Alpha (HI)", VoiceGender.FEMALE),
    # Italian
    _voice("im_nicola", "it", "Nicola (IT)", VoiceGender.MALE),
    _voice("if_sara", "it", "Sara (IT)", VoiceGender.FEMALE),
    # Japanese
    _voice("jm_kumo", "ja", "Kumo (JA)", VoiceGender.MALE),
    _voice("jf_alpha", "ja", "Alpha (JA)", VoiceGender.FEMALE),
    # Brazilian Portuguese
    _voice("pm_alex", "pt-BR", "Alex (BR)", VoiceGender.MALE),
    _voice("pf_dora", "pt-BR", "Dora (BR)", VoiceGender.FEMALE),
    # Mandarin Chinese
    _voice("zm_yunxi", "zh", "Yunxi (ZH)", VoiceGender.MALE),
    _voice("zf_xiaoxiao", "zh", "Xiaoxiao (ZH)", VoiceGender.FEMALE),
)
