"""What a curated audio.cpp model commits beyond the shared entry: a voice
model's voices, a recogniser's languages, and the memory either takes while it
works, because the server reports none of them."""

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from modules.llm.catalog.local.manifest.strict import STRICT
from modules.llm.model_type import ModelType

# A language as the screen names it: ISO 639-1, or 639-3 where 639-1 has none.
LanguageCode = Annotated[str, Field(pattern=r"^[a-z]{2,3}$")]


@dataclass(frozen=True)
class RecogniserFamily:
    """What a family takes at the pinned server, which fails a request naming
    anything else."""

    locales: frozenset[str]
    request_options: frozenset[str]


# audio.cpp v0.8.2: each family's model spec lists its locales, and its
# loader.cpp its request options.
# fmt: off
RECOGNISER_FAMILIES: dict[str, RecogniserFamily] = {
    "nemotron_asr": RecogniserFamily(
        frozenset({
            "ar-AR", "bg-BG", "cs-CZ", "da-DK", "de-DE", "el-GR", "en-GB", "en-US",
            "es-ES", "es-US", "et-EE", "fi-FI", "fr-CA", "fr-FR", "he-IL", "hi-IN",
            "hr-HR", "hu-HU", "it-IT", "ja-JP", "ko-KR", "lt-LT", "lv-LV", "mt-MT",
            "nb-NO", "nl-NL", "nn-NO", "pl-PL", "pt-BR", "pt-PT", "ro-RO", "ru-RU",
            "sk-SK", "sl-SI", "sv-SE", "th-TH", "tr-TR", "uk-UA", "vi-VN", "zh-CN",
        }),
        frozenset({"language", "lookahead_tokens", "max_tokens", "keep_language_tags"}),
    ),
    "canary_asr": RecogniserFamily(
        frozenset({"en", "de", "es", "fr"}),
        frozenset({
            "language", "target_language", "pnc", "max_tokens",
            "audio_chunk_mode", "audio_chunk_duration_sec",
        }),
    ),
}
# fmt: on
_NOTHING_KNOWN = RecogniserFamily(frozenset(), frozenset())


class Voice(BaseModel):
    model_config = STRICT

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    # The form groups voices by it; each model's own voice ids or config say it.
    gender: Literal["female", "male"]
    # None: the voice speaks every language the model lists (Supertonic).
    language: str | None = None


class ChunkStep(BaseModel):
    """A smaller text chunk and the peak it measured, for a tight machine."""

    model_config = STRICT

    text_chunk_size: int = Field(gt=0)
    peak_mb: int = Field(gt=0)


class AudioDefaults(BaseModel):
    model_config = STRICT

    origin: str = Field(min_length=1)
    sample_rate: int = Field(gt=0)
    # Measured on the server with every chunk full, at its default chunk size:
    # the working memory is sized for a request's longest chunk.
    peak_mb: int = Field(gt=0)
    chunk_steps: list[ChunkStep] = Field(default_factory=list)
    languages: list[str] = Field(min_length=1)
    # A podcast gives each of its two speakers a voice.
    voices: list[Voice] = Field(min_length=2)

    @model_validator(mode="after")
    def _voices_hold_together(self) -> "AudioDefaults":
        ids = [v.id for v in self.voices]
        if len(ids) != len(set(ids)):
            raise ValueError("a voice is listed twice")
        stray = {v.language for v in self.voices if v.language} - set(self.languages)
        if stray:
            raise ValueError(f"voices speak unlisted languages: {sorted(stray)}")
        return self


class TranscriptionDefaults(BaseModel):
    model_config = STRICT

    origin: str = Field(min_length=1)
    # What every window is resampled to before it is sent.
    sample_rate: int = Field(gt=0)
    # Measured on the first request, the load included: admission reads it.
    peak_mb: int = Field(gt=0)
    # The longest window a request carries; a request's memory grows with it.
    window_s: int = Field(gt=0)
    detects_language: bool
    # The languages the screen lists: those measured usable, not all it knows.
    languages: list[LanguageCode] = Field(min_length=1)
    # The locale the family takes for each listed language.
    family_codes: dict[LanguageCode, str] = Field(default_factory=dict)
    # Locales it may detect without being listed for them, by language.
    detected_only: dict[LanguageCode, str] = Field(default_factory=dict)
    # Written as the server entry's default_request_options: the multipart
    # routes take no options of their own.
    request_options: dict[str, bool | int | str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _languages_hold_together(self) -> "TranscriptionDefaults":
        listed = set(self.languages)
        if len(self.languages) != len(listed):
            raise ValueError("a language is listed twice")
        if stray := set(self.family_codes) - listed:
            raise ValueError(f"locales for unlisted languages: {sorted(stray)}")
        if both := set(self.detected_only) & listed:
            raise ValueError(f"detected only, yet listed: {sorted(both)}")
        return self

    def unknown_to(self, family: str) -> list[str]:
        """The locales and request options `family` does not take."""
        known = RECOGNISER_FAMILIES.get(family, _NOTHING_KNOWN)
        locales = {*self.family_codes.values(), *self.detected_only.values()}
        return sorted(
            (locales - known.locales)
            | (set(self.request_options) - known.request_options)
        )

    def without_locale(self, family: str) -> list[str]:
        """Listed languages `family` would get no locale for: pinning one would
        send the bare code, which a family that takes locales fails on."""
        known = RECOGNISER_FAMILIES.get(family, _NOTHING_KNOWN)
        if not known.locales:
            return []
        return [code for code in self.languages if code not in self.family_codes]


ENTRY_OWNS = frozenset({"audio", "transcription"})
ENTRY_REQUIRES: frozenset[str] = frozenset()
# One of these, never both: a voice model has voices, a recogniser languages.
ENTRY_REQUIRES_ONE_OF = frozenset({"audio", "transcription"})
# The one each type's entry carries.
ENTRY_BLOCK_FOR = (
    (ModelType.AUDIO_GEN, "audio"),
    (ModelType.SPEECH_TO_TEXT, "transcription"),
)
