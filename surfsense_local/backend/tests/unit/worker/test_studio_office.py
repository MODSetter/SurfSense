"""The office seam runs the model's generated builder and stores its bytes."""

import pytest

from worker.studio import generate, office
from worker.studio.artifact import Source
from worker.studio.office import runner

pytestmark = pytest.mark.unit


def _model(raw: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for the selected model, returning fixed code."""
    monkeypatch.setattr(generate, "run_model", lambda *a, **k: raw)


def test_render_executes_generated_code_and_keeps_its_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The script sets output_bytes/title/summary; render() lifts them into a Built."""
    _model(
        "```python\n"
        "output_bytes = b'%PDF-1.7 fake'\n"
        "title = 'Cassini'\n"
        "summary = '# Cassini\\n\\nArrival in 2004.'\n"
        "```",
        monkeypatch,
    )

    built = office.render(None, "pdf", [Source(1, "Saturn", "rings")], None)

    assert built.primary == b"%PDF-1.7 fake"
    assert built.primary_mime == "application/pdf"
    assert built.primary_filename == "cassini.pdf"
    assert built.title == "Cassini"
    assert "Arrival in 2004." in built.markdown


def test_render_uses_the_picked_formats_mime_and_extension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The user's button fixes the type: a docx job stores a .docx, not whatever."""
    _model("output_bytes = b'PK\\x03\\x04'\ntitle = 'Deck'", monkeypatch)

    built = office.render(None, "docx", [], None)

    assert built.primary_filename == "deck.docx"
    assert built.primary_mime.endswith("wordprocessingml.document")
    assert built.markdown == "# Deck"  # summary falls back to the title


def test_code_that_forgets_output_bytes_fails_the_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing the contract variable is a clear failure, not an empty file."""
    _model("title = 'oops'", monkeypatch)

    with pytest.raises(RuntimeError, match="output_bytes"):
        office.render(None, "pdf", [], None)


def test_code_that_raises_surfaces_the_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """A crash inside the generated code becomes the job's error message."""
    _model("raise ValueError('bad layout')", monkeypatch)

    with pytest.raises(RuntimeError, match="bad layout"):
        office.render(None, "pptx", [], None)


def test_execute_times_out_a_hanging_script(monkeypatch: pytest.MonkeyPatch) -> None:
    """A script that never returns is killed by the timeout, not left to hang."""
    monkeypatch.setattr(runner, "TIMEOUT_SECONDS", 0.2)

    with pytest.raises(RuntimeError, match="did not finish"):
        runner.execute("import time\nwhile True:\n    time.sleep(0.05)")


def test_each_format_carries_its_skill_and_library() -> None:
    """Every office folder loaded a non-empty SKILL.md and names its library."""
    for spec in office.OFFICE.values():
        assert spec.skill.strip()
        assert spec.library in {"python-docx", "python-pptx", "xlsxwriter", "reportlab"}
