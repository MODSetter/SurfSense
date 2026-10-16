"""Which locale a request names, and which language a text came back in."""

import pytest

from modules.llm.catalog.local.manifest import load_local_manifest
from modules.llm.transcription.languages import heard, requested_locale

pytestmark = pytest.mark.unit

(NEMOTRON,) = [
    m.transcription
    for m in load_local_manifest().models
    if m.id == "nemotron-3.5-asr-streaming-0.6b"
]


@pytest.mark.parametrize(
    ("intent", "locale"),
    [
        pytest.param("auto", None, id="auto lets the model detect"),
        pytest.param("ja", "ja-JP", id="a listed language as its family locale"),
        pytest.param("pt", "pt-BR", id="the locale the entry chose for it"),
        pytest.param("et", None, id="one it is not listed for falls back to auto"),
    ],
)
def test_the_request_names_the_family_locale_or_nothing(
    intent: str, locale: str | None
) -> None:
    """The server fails a locale the family does not take."""
    assert requested_locale(intent, NEMOTRON) == locale


def test_the_last_tag_names_the_language_and_every_tag_goes() -> None:
    """Nemotron tags each sentence; a speaker who switched ends on the last."""
    text, language = heard(
        "Hola a todos. <es-ES> And now in English. <en-US>", "auto", NEMOTRON
    )

    assert (text, language) == ("Hola a todos. And now in English.", "en")


def test_a_locale_maps_back_by_its_language() -> None:
    """pt-PT is not the locale the entry sends, but it is still Portuguese."""
    assert heard("Bom dia. <pt-PT>", "auto", NEMOTRON) == ("Bom dia.", "pt")


def test_a_language_it_only_detects_keeps_its_code() -> None:
    """Swedish is listed; Estonian is detected only, at lower accuracy."""
    assert heard("Tere. <et-EE>", "auto", NEMOTRON) == ("Tere.", "et")


def test_a_locale_in_neither_map_is_not_identified() -> None:
    """The header then says the language was not identified."""
    assert heard("Sawubona. <zu-ZA>", "auto", NEMOTRON) == ("Sawubona.", None)


def test_with_no_tag_the_language_is_the_intent() -> None:
    """The user said which; nothing in the text overrules it."""
    assert heard("Bonjour à tous", "de", NEMOTRON) == ("Bonjour à tous", "de")


@pytest.mark.parametrize(
    ("text", "language"),
    [
        pytest.param("नमस्ते दुनिया", "hi", id="Devanagari"),
        pytest.param("收入增长了百分之十二", "zh", id="Han alone"),
        pytest.param("今日は会議があります", "ja", id="Han with kana"),
        pytest.param("안녕하세요 여러분", "ko", id="Hangul"),
        pytest.param("مرحبا بالجميع", "ar", id="Arabic"),
        pytest.param(
            "Привет всем", None, id="Cyrillic: Russian, Ukrainian or Bulgarian"
        ),
        pytest.param("Bonjour à tous", None, id="Latin: any of twenty"),
    ],
)
def test_with_no_tag_under_auto_a_script_only_one_language_writes_names_it(
    text: str, language: str | None
) -> None:
    """Measured: a third of Kokoro's sentences came back with no tag, the
    Hindi among them, past the 1 in 10 at which the proposal reads the script."""
    assert heard(text, "auto", NEMOTRON) == (text, language)
