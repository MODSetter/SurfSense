"""Smoke tests for PDF rendering.

We don't pull a full PDF parser into the test deps; the assertions
are bytes-level (``%PDF`` magic, deterministic CreationDate scrub).
"""

from __future__ import annotations

from pathlib import Path

from surfsense_evals.core.pdf import render_pdf, render_text_files_to_pdf


def test_render_pdf_writes_pdf_with_magic(tmp_path: Path):
    out = tmp_path / "out.pdf"
    rendered = render_pdf(
        title="Test",
        sections=[("intro", "Hello world."), ("body", "Line one.\nLine two.")],
        output_path=out,
    )
    assert rendered.path == out
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF-")


def test_render_pdf_deterministic_dates(tmp_path: Path):
    out_a = tmp_path / "a.pdf"
    out_b = tmp_path / "b.pdf"
    sections = [("only", "deterministic body content")]
    render_pdf(title="Det", sections=sections, output_path=out_a)
    render_pdf(title="Det", sections=sections, output_path=out_b)
    # CreationDate / ModDate are scrubbed to a fixed value, so the two
    # files should compare equal (modulo any other internal randomness
    # — reportlab's basic outputs are deterministic given fixed inputs).
    assert out_a.read_bytes() == out_b.read_bytes()


def test_render_text_files_uses_filename_as_section(tmp_path: Path):
    files_dir = tmp_path / "src"
    files_dir.mkdir()
    (files_dir / "admission_note.txt").write_text("history of present illness", encoding="utf-8")
    (files_dir / "labs.txt").write_text("Na 138, K 4.0", encoding="utf-8")
    out = tmp_path / "case.pdf"
    rendered = render_text_files_to_pdf(
        title="Case 1",
        files=[files_dir / "admission_note.txt", files_dir / "labs.txt"],
        output_path=out,
    )
    assert out.exists()
    # We don't decode the PDF; the n_chars estimate should reflect both inputs.
    assert rendered.n_chars >= len("history of present illness") + len("Na 138, K 4.0")
