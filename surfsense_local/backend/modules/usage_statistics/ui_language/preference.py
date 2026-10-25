"""The language the user picked in Settings > General, as Electron main stores it."""

import json
from pathlib import Path

# electron/src/main/i18n/locale-prefs.ts writes it in Electron's userData.
FILE_NAME = "locale-prefs.json"
# electron/src/main/i18n/locales.ts; anything else Electron reads as "system".
_LOCALES = {"en", "de", "es", "fr", "hi", "ja", "ko", "pt-BR", "ru", "zh-CN", "en-XA"}


def stored_preference(electron_dir: Path) -> str:
    """A locale code, or "system" when none is stored or Electron would not take it."""
    try:
        raw = json.loads((electron_dir / FILE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "system"
    locale = raw.get("locale") if isinstance(raw, dict) else None
    return locale if locale in _LOCALES else "system"
