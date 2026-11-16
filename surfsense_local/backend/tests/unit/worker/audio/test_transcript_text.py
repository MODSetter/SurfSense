"""The transcript a recording's content holds: one header line, then a paragraph
per window starting with its time, so every chunk the chunker cuts at a blank
line starts with when it was said."""

import pytest

from modules.llm.catalog.local.manifest import load_local_manifest
from worker.ingestion.audio.language_names import english_name
from worker.ingestion.audio.model_name import model_name
from worker.ingestion.audio.transcript_text import (
    HeardWindow,
    header_language,
    paragraph_lines,
    transcript_markdown,
)

pytestmark = pytest.mark.unit

LISTED = ("en", "es", "ja")
GUIDE = "[hh:mm:ss] marks where each passage starts."


def heard(start_s: float, text: str, language: str | None) -> HeardWindow:
    """A 20 s window written down."""
    return HeardWindow(
        start_s=start_s, end_s=start_s + 20, text=text, language=language
    )


def test_each_window_is_a_paragraph_under_one_header() -> None:
    """The header names the file, its length, the language and the model."""
    text = transcript_markdown(
        title="meeting.mp3",
        seconds=2530.4,
        windows=[heard(0.4, "Hello all.", "ja"), heard(26.0, "Next item.", "ja")],
        language="Japanese (detected)",
        model="Nemotron 3.5 ASR Streaming 0.6B",
    )

    assert text == (
        "Transcript of meeting.mp3 · 42:10 · Japanese (detected) · "
        f"Nemotron 3.5 ASR Streaming 0.6B. {GUIDE}\n\n"
        "[00:00:00] Hello all.\n\n"
        "[00:00:26] Next item.\n"
    )


def test_hours_show_in_the_length_and_every_time() -> None:
    """A long recording's places stay exact past the first hour."""
    text = transcript_markdown(
        title="lecture.flac",
        seconds=3723.0,
        windows=[heard(3661.9, "Questions?", "en")],
        language="English",
        model="m",
    )

    assert text.startswith("Transcript of lecture.flac · 1:02:03 · English · m.")
    assert text.endswith("[01:01:01] Questions?\n")


def test_a_window_with_nothing_written_has_no_paragraph() -> None:
    """A cough the detector let through leaves no empty timestamp."""
    text = transcript_markdown(
        title="a.wav",
        seconds=60,
        windows=[heard(0, "", None), heard(30, "Right.", "en")],
        language="English (detected)",
        model="m",
    )

    assert text.count("[00:") == 1


@pytest.mark.parametrize(
    ("pinned", "languages", "label"),
    [
        # Set by the user: what they said they speak.
        ("ja", ["en", "en"], "Japanese"),
        (None, ["ja", "en", "ja"], "Japanese (detected)"),
        # Detected, but not one the model is listed for.
        (None, ["sv", "sv"], "Swedish (detected) · lower accuracy with this model"),
        (None, [None, None], "language not identified"),
    ],
)
def test_the_header_names_the_language_most_windows_were_heard_in(
    pinned: str | None, languages: list[str | None], label: str
) -> None:
    """Each window keeps its own; the header takes the majority."""
    windows = [heard(n * 30, "words", code) for n, code in enumerate(languages)]

    assert header_language(windows, pinned, LISTED) == label


def test_a_tie_goes_to_the_language_heard_for_longer() -> None:
    """Two windows each: the longer speech names the recording."""
    windows = [
        heard(0, "a", "es"),
        heard(30, "b", "en"),
        heard(60, "c", "es"),
        HeardWindow(start_s=90, end_s=118, text="d", language="en"),
    ]

    assert header_language(windows, None, LISTED) == "English (detected)"


def test_every_language_a_recogniser_may_answer_in_has_a_name() -> None:
    """A curated model's listed and detected languages all read in the header."""
    codes = {
        code
        for model in load_local_manifest().models
        if model.transcription is not None
        for code in (*model.transcription.languages, *model.transcription.detected_only)
    }

    assert codes
    assert all(english_name(code) != code for code in codes)


def test_the_model_is_named_as_settings_shows_it() -> None:
    """The server knows it by its file; the header by the curated entry."""
    assert model_name("nemotron-3.5-asr-streaming-0.6b-q8_0") == (
        "Nemotron 3.5 ASR Streaming 0.6B"
    )
    assert model_name("someone-elses-model") == "someone-elses-model"


def test_each_paragraph_is_one_line_where_its_segment_says() -> None:
    """segments.json points at the line a chunk records, for seeking later."""
    windows = [
        heard(0, "First\nline.", "en"),
        heard(30, "", None),
        heard(60, "Second.", "en"),
    ]
    text = transcript_markdown(
        title="a.wav", seconds=90, windows=windows, language="English", model="m"
    )

    lines = text.splitlines()
    assert paragraph_lines(windows) == [3, None, 5]
    assert lines[2] == "[00:00:00] First line."
    assert lines[4] == "[00:01:00] Second."
