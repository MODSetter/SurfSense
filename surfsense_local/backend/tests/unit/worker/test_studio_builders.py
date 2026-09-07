"""Builders render deterministically, and the registry matches the API catalog."""

import pytest

from modules.artifacts.formats import FORMATS
from worker.studio.builders import BUILDERS
from worker.studio.builders.summary import build
from worker.studio.builders.util import parse_json

pytestmark = pytest.mark.unit

# Office formats are ZIP containers; every valid one starts with the ZIP magic.
ZIP_MAGIC = b"PK\x03\x04"


def test_every_buildable_format_has_a_builder() -> None:
    """The dependency-free catalog and the worker registry cannot drift apart."""
    buildable = {fmt.key for fmt in FORMATS if not fmt.requires_key}
    assert set(BUILDERS) == buildable


def test_a_summary_takes_its_title_from_the_first_h1() -> None:
    """The document title comes from the model's H1, so the list reads well."""
    built = build("# Saturn's rings\n\nThey are mostly ice.", [])

    assert built.title == "Saturn's rings"
    assert built.markdown.startswith("# Saturn's rings")
    assert built.primary is None  # the markdown is the body, not a file


def test_a_summary_without_a_heading_still_has_a_title() -> None:
    """A model that skips the H1 still yields a named, openable artifact."""
    assert build("Just prose, no heading.", []).title == "Summary"


def test_parse_json_survives_fences_and_surrounding_prose() -> None:
    """Local models wrap JSON in prose and fences; the object is still recovered."""
    raw = 'Sure!\n```json\n{"title": "T", "sections": []}\n```\nHope that helps.'
    assert parse_json(raw) == {"title": "T", "sections": []}


def test_parse_json_rejects_a_non_object() -> None:
    """A builder must fail loudly, not render half a spec, on bad output."""
    with pytest.raises(ValueError, match="JSON"):
        parse_json("not json at all")


@pytest.mark.parametrize("key", ["docx", "pptx", "xlsx"])
def test_office_formats_build_a_valid_container(key: str) -> None:
    """docx/pptx/xlsx are real Office files: a ZIP with the source text inside."""
    specs = {
        "docx": '{"title": "Cassini", "sections": '
        '[{"heading": "Arrival", "paragraphs": ["Reached Saturn in 2004."]}]}',
        "pptx": '{"title": "Cassini", "slides": '
        '[{"title": "Arrival", "bullets": ["Reached Saturn in 2004."]}]}',
        "xlsx": '{"title": "Cassini", "sheets": '
        '[{"name": "Facts", "columns": ["Year"], "rows": [["2004"]]}]}',
    }
    built = BUILDERS[key].build(specs[key], [])

    assert built.title == "Cassini"
    assert built.primary is not None and built.primary.startswith(ZIP_MAGIC)
    assert built.primary_filename and built.primary_filename.endswith(f".{key}")
    assert "Arrival" in built.markdown or "Facts" in built.markdown


def test_pdf_builds_a_real_pdf_with_the_source_title() -> None:
    """A pdf artifact is a downloadable file starting with the PDF magic."""
    raw = '{"title": "Cassini", "sections": [{"heading": "H", "paragraphs": ["P."]}]}'
    built = BUILDERS["pdf"].build(raw, [])

    assert built.primary is not None and built.primary.startswith(b"%PDF")
    assert built.primary_mime == "application/pdf"
    assert built.primary_filename == "cassini.pdf"


def test_html_escapes_model_text_so_it_cannot_carry_a_script() -> None:
    """The model supplies text only; markup it sends is neutralised, not run."""
    raw = '{"title": "T", "sections": [{"heading": "H", "paragraphs": ["<script>x</script>"]}]}'
    built = BUILDERS["html"].build(raw, [])

    assert built.primary_mime == "text/html"
    body = built.primary.decode()
    assert "<script>" not in body
    assert "&lt;script&gt;" in body


def test_mindmap_renders_a_nested_outline_and_no_file() -> None:
    """A mind map is a markdown body Markmap reads; there is nothing to download."""
    raw = '{"title": "Saturn", "nodes": [{"label": "Rings", "children": [{"label": "Ice"}]}]}'
    built = BUILDERS["mindmap"].build(raw, [])

    assert built.primary is None
    assert "# Saturn" in built.markdown
    assert "- Rings" in built.markdown
    assert "  - Ice" in built.markdown


def test_podcast_voices_a_two_host_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The transcript is the searchable body; the synthesised WAV is the file."""
    monkeypatch.setattr("worker.studio.tts.synthesize", lambda turns: b"RIFFfake")
    raw = (
        '{"title": "Saturn", "turns": [{"speaker": "A", "text": "Hi."}, '
        '{"speaker": "B", "text": "Tell me more."}]}'
    )
    built = BUILDERS["podcast"].build(raw, [])

    assert built.primary == b"RIFFfake"
    assert built.primary_mime == "audio/wav"
    assert built.primary_filename == "saturn.wav"
    assert "**A:** Hi." in built.markdown
    assert "**B:** Tell me more." in built.markdown


def test_podcast_without_the_voice_pack_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A machine lacking Kokoro gets a clear reason, like the parser-pack path."""
    monkeypatch.setattr(
        "worker.studio.tts.missing_kokoro_files", lambda: ["kokoro-v1.0.onnx"]
    )
    raw = '{"title": "T", "turns": [{"speaker": "A", "text": "Hi."}]}'

    with pytest.raises(RuntimeError, match="Kokoro"):
        BUILDERS["podcast"].build(raw, [])


def test_flashcards_and_quiz_project_to_readable_markdown() -> None:
    """The searchable body carries the content, so both index and read plainly."""
    cards = BUILDERS["flashcards"].build(
        '{"title": "Deck", "cards": [{"front": "Q?", "back": "A."}]}', []
    )
    assert cards.primary is None
    assert "Q?" in cards.markdown and "A." in cards.markdown

    quiz = BUILDERS["quiz"].build(
        '{"title": "Test", "questions": [{"question": "Q?", '
        '"options": ["a", "b"], "answer": "a"}]}',
        [],
    )
    assert "Q?" in quiz.markdown and "Answer: a" in quiz.markdown
