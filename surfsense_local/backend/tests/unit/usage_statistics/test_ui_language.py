"""The interface language, mirrored from Electron's choice and reported as en, ja, de or other."""

import json
from pathlib import Path

import pytest

from modules.usage_statistics import ui_language as module
from modules.usage_statistics.ui_language import resolve_system, ui_language

pytestmark = pytest.mark.unit


def prefer(electron_dir: Path, locale: str) -> Path:
    """Store a choice the way Settings > General does."""
    electron_dir.mkdir(exist_ok=True)
    (electron_dir / "locale-prefs.json").write_text(json.dumps({"locale": locale}))
    return electron_dir


@pytest.mark.parametrize(
    ("locale", "reported"),
    [("ja", "ja"), ("de", "de"), ("en", "en"), ("pt-BR", "other"), ("zh-CN", "other")],
)
def test_a_language_picked_in_settings_is_the_one_reported(
    tmp_path: Path, locale: str, reported: str
) -> None:
    """Every catalog but the three named is "other"."""
    assert ui_language(prefer(tmp_path / "electron", locale)) == reported


@pytest.mark.parametrize(
    ("languages", "reported"),
    [
        (["de-AT", "en-US"], "de"),
        (["it-IT", "ja-JP"], "ja"),
        (["it-IT"], "en"),
        (["zh-Hant-TW", "fr-FR"], "other"),
        (["ja_JP"], "ja"),
    ],
)
def test_the_system_language_resolves_as_electron_resolves_it(
    languages: list[str], reported: str
) -> None:
    """The first language with a catalog wins; none means the app shows English."""
    assert resolve_system(languages) == reported


def test_system_follows_the_os_and_an_unreadable_os_is_other(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no stored choice the OS decides; if it cannot be read nothing is guessed."""
    monkeypatch.setattr(module, "system_languages", lambda: ["de-DE"])
    assert ui_language(tmp_path / "electron") == "de"

    monkeypatch.setattr(module, "system_languages", lambda: [])
    assert ui_language(prefer(tmp_path / "electron", "system")) == "other"


def test_a_stored_value_electron_would_refuse_reads_as_system(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Electron reads an unknown code as "system", so this does too."""
    monkeypatch.setattr(module, "system_languages", lambda: ["ja-JP"])

    assert ui_language(prefer(tmp_path / "electron", "it")) == "ja"
