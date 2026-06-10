"""Resolve the brief's language without spending tokens at the gate.

The chain mirrors the agreed policy: reuse the language the user last chose, and
otherwise default to English (which the user can still override in the brief). We
deliberately never guess the language from the source content — proposing a
language the user did not ask for is worse than a predictable default.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

# What a brand-new user with no signal gets, and what every chain ends on.
DEFAULT_LANGUAGE = "en"


@dataclass(frozen=True, slots=True)
class LanguageContext:
    """Signals available when proposing a language for a fresh podcast."""

    last_used: str | None = None


class LanguageResolver(ABC):
    """One step in the language fallback chain."""

    @abstractmethod
    def resolve(self, context: LanguageContext) -> str | None:
        """Return a language tag, or ``None`` to defer to the next resolver."""


class LastUsedLanguage(LanguageResolver):
    """Reuse the language from the user's previous podcast."""

    def resolve(self, context: LanguageContext) -> str | None:
        return context.last_used


class DefaultLanguage(LanguageResolver):
    """Terminal step: always yields the default so the chain never fails."""

    def resolve(self, context: LanguageContext) -> str | None:
        return DEFAULT_LANGUAGE


# Order encodes the policy; prepend stronger signals here as they appear.
DEFAULT_LANGUAGE_CHAIN: tuple[LanguageResolver, ...] = (
    LastUsedLanguage(),
    DefaultLanguage(),
)


def resolve_language(
    context: LanguageContext,
    chain: tuple[LanguageResolver, ...] = DEFAULT_LANGUAGE_CHAIN,
) -> str:
    """Walk ``chain`` and return the first language a resolver yields."""
    for resolver in chain:
        language = resolver.resolve(context)
        if language:
            return language.strip()
    # The default resolver guarantees a value; this guards a misconfigured chain.
    return DEFAULT_LANGUAGE
