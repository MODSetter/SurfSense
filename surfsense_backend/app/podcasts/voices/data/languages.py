"""Curated languages offered when a roster has wildcard (any-language) voices.

OpenAI-style multilingual voices speak whatever language the text is in, so
there is no provider list to enumerate. This is the set the brief form offers
up front for such providers; it is an offering, not a limit — the API flags
``allows_custom`` so users can enter any BCP-47 tag beyond it.
"""

from __future__ import annotations

COMMON_LANGUAGES: tuple[str, ...] = (
    "ar",
    "bn",
    "de",
    "en",
    "es",
    "fr",
    "hi",
    "id",
    "it",
    "ja",
    "ko",
    "nl",
    "pl",
    "pt",
    "ru",
    "sw",
    "th",
    "tr",
    "uk",
    "vi",
    "zh",
)
