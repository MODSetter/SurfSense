"""Tests for ``render_pdf_with_images`` — covers image embedding +
deterministic byte output, mirroring ``test_pdf_render.py`` for the
text-only path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from surfsense_evals.core.pdf import PdfImage, render_pdf_with_images


@pytest.fixture
def tiny_png(tmp_path: Path) -> Path:
    """Generate a real 4x4 PNG via Pillow — embeds cleanly in reportlab.

    Hand-crafted PNG headers tend to fail PIL's strict decoder, so we
    delegate to Pillow which is already a transitive dep of reportlab.
    """

    from PIL import Image as PILImage

    p = tmp_path / "pixel.png"
    PILImage.new("RGB", (4, 4), color=(128, 128, 128)).save(p, format="PNG")
    return p


class TestRenderPdfWithImages:
    def test_renders_pdf_with_no_images(self, tmp_path: Path) -> None:
        out = tmp_path / "out.pdf"
        rendered = render_pdf_with_images(
            title="Test",
            sections=[("Heading", "Body text here.", None)],
            output_path=out,
        )
        assert rendered.path == out
        assert out.exists()
        assert out.read_bytes().startswith(b"%PDF-")

    def test_renders_pdf_with_one_image(self, tmp_path: Path, tiny_png: Path) -> None:
        out = tmp_path / "out.pdf"
        render_pdf_with_images(
            title="Test",
            sections=[("Case", "Body text.", [PdfImage(path=tiny_png, caption="A pixel")])],
            output_path=out,
        )
        assert out.exists()
        assert out.stat().st_size > 200  # not empty

    def test_deterministic_bytes(self, tmp_path: Path, tiny_png: Path) -> None:
        out_a = tmp_path / "a.pdf"
        out_b = tmp_path / "b.pdf"
        sections = [
            ("Case", "Some text.", [PdfImage(path=tiny_png, caption="cap")]),
            ("Options", "A) one\nB) two", None),
        ]
        render_pdf_with_images(title="Test", sections=sections, output_path=out_a)
        render_pdf_with_images(title="Test", sections=sections, output_path=out_b)
        assert out_a.read_bytes() == out_b.read_bytes()

    def test_skips_invalid_image_silently(self, tmp_path: Path) -> None:
        """A bad image path should not abort the whole PDF render."""

        out = tmp_path / "out.pdf"
        render_pdf_with_images(
            title="Test",
            sections=[("Case", "Text", [PdfImage(path=tmp_path / "nope.jpg", caption="x")])],
            output_path=out,
        )
        assert out.exists()
        assert out.read_bytes().startswith(b"%PDF-")
