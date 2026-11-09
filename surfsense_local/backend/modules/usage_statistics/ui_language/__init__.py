"""Which language the app's interface shows, in the report's four values.

Electron main owns the locale; this mirrors its choice (electron/src/main/i18n/
resolve-locale.ts) from the preference it stores and the system's languages.
"""

from collections.abc import Sequence
from pathlib import Path

from modules.usage_statistics.ui_language.preference import stored_preference
from modules.usage_statistics.ui_language.system_languages import system_languages

# The catalogs the app ships (frontend/src/i18n/locales.ts), by base language.
_CATALOG_BASES = {"en", "de", "es", "fr", "hi", "ja", "ko", "pt", "ru", "zh"}
_TRADITIONAL = {"hant", "tw", "hk", "mo"}
_REPORTED = {"en", "ja", "de"}


def ui_language(electron_dir: Path) -> str:
    preference = stored_preference(electron_dir)
    if preference != "system":
        return _reported(preference)
    languages = system_languages()
    # Nothing readable: say so as "other" rather than guess English.
    return "other" if not languages else resolve_system(languages)


def resolve_system(languages: Sequence[str]) -> str:
    """The first system language with a catalog, else English, as Electron picks it."""
    for tag in languages:
        base, *rest = tag.lower().replace("_", "-").split("-")
        if base == "zh" and any(part in _TRADITIONAL for part in rest):
            continue
        if base in _CATALOG_BASES:
            return _reported(base)
    return "en"


def _reported(locale: str) -> str:
    base = locale.lower().split("-")[0]
    return base if base in _REPORTED else "other"
