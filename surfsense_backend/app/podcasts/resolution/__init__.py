"""Resolution: deterministic default chains for a fresh brief.

Turns the user's last-used preferences into concrete language and voice
defaults, so the brief gate opens pre-filled and most users approve without
editing.
"""

from __future__ import annotations

from .language import (
    DEFAULT_LANGUAGE,
    DEFAULT_LANGUAGE_CHAIN,
    LanguageContext,
    LanguageResolver,
    resolve_language,
)
from .voices import VoiceResolutionError, resolve_voices

__all__ = [
    "DEFAULT_LANGUAGE",
    "DEFAULT_LANGUAGE_CHAIN",
    "LanguageContext",
    "LanguageResolver",
    "VoiceResolutionError",
    "resolve_language",
    "resolve_voices",
]
