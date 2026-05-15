"""Unit tests for the picture_describer module.

Covers:

- :func:`describe_pictures` -- the PDF image walker + per-image vision
  LLM call (structured output split into ``ocr_text`` and
  ``description``);
- :func:`inject_descriptions_inline` -- in-place replacement of image
  placeholders / captions in the parser markdown;
- :func:`merge_descriptions_into_markdown` -- the top-level helper
  that inlines what it can and appends what it can't;
- :func:`render_appended_section` -- the appended-fallback renderer.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.etl_pipeline.picture_describer import (
    PictureDescription,
    PictureExtractionResult,
    describe_pictures,
    inject_descriptions_inline,
    merge_descriptions_into_markdown,
    render_appended_section,
)

pytestmark = pytest.mark.unit


def _make_image_obj(name: str, data: bytes):
    """Mimic pypdf's ImageFile object shape for the bits we use."""
    img = MagicMock()
    img.name = name
    img.data = data
    return img


# ---------------------------------------------------------------------------
# describe_pictures: short-circuits
# ---------------------------------------------------------------------------


async def test_describe_pictures_no_op_for_non_pdf(tmp_path):
    """Non-PDF files are silently no-op'd; we don't try to extract images."""
    docx_file = tmp_path / "report.docx"
    docx_file.write_bytes(b"PK fake docx")

    fake_llm = AsyncMock()
    result = await describe_pictures(str(docx_file), "report.docx", fake_llm)

    assert result.descriptions == []
    assert result.skipped_too_large == 0
    fake_llm.ainvoke.assert_not_called()


async def test_describe_pictures_no_op_when_vision_llm_is_none(tmp_path):
    """If the caller didn't provide a vision LLM, we no-op even for PDFs."""
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    result = await describe_pictures(str(pdf_file), "report.pdf", None)
    assert result.descriptions == []


async def test_describe_pictures_no_op_for_pdf_with_no_images(tmp_path, mocker):
    """A PDF that pypdf can open but contains zero images returns empty."""
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    fake_reader = MagicMock()
    fake_reader.pages = [MagicMock(images=[]), MagicMock(images=[])]
    mocker.patch("pypdf.PdfReader", return_value=fake_reader)

    fake_llm = AsyncMock()
    result = await describe_pictures(str(pdf_file), "report.pdf", fake_llm)

    assert result.descriptions == []
    fake_llm.ainvoke.assert_not_called()


# ---------------------------------------------------------------------------
# describe_pictures: happy paths
# ---------------------------------------------------------------------------


async def test_describe_pictures_runs_vision_llm_per_image(tmp_path, mocker):
    """Every eligible image gets exactly one description-only vision call."""
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    img_a = _make_image_obj("Im0.jpeg", b"\xff\xd8\xff\xe0" + b"\xab" * 2000)
    img_b = _make_image_obj("Im1.png", b"\x89PNG\r\n\x1a\n" + b"\xcd" * 2000)
    page1 = MagicMock(images=[img_a])
    page2 = MagicMock(images=[img_b])

    fake_reader = MagicMock()
    fake_reader.pages = [page1, page2]
    mocker.patch("pypdf.PdfReader", return_value=fake_reader)

    parse_mock = mocker.patch(
        "app.etl_pipeline.parsers.vision_llm.parse_image_for_description",
        new=AsyncMock(side_effect=["Description A", "Description B"]),
    )

    fake_llm = MagicMock()
    result = await describe_pictures(str(pdf_file), "report.pdf", fake_llm)

    assert len(result.descriptions) == 2
    by_name = {d.name: d.description for d in result.descriptions}
    assert by_name == {"Im0.jpeg": "Description A", "Im1.png": "Description B"}
    assert all(d.page_number in (1, 2) for d in result.descriptions)
    assert parse_mock.await_count == 2


async def test_describe_pictures_dedups_by_hash(tmp_path, mocker):
    """An image that appears N times in the PDF is described once."""
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    payload = b"\x89PNG\r\n\x1a\n" + b"\x42" * 2000
    img = _make_image_obj("logo.png", payload)
    page1 = MagicMock(images=[img])
    page2 = MagicMock(images=[_make_image_obj("logo.png", payload)])
    page3 = MagicMock(images=[_make_image_obj("logo.png", payload)])

    fake_reader = MagicMock()
    fake_reader.pages = [page1, page2, page3]
    mocker.patch("pypdf.PdfReader", return_value=fake_reader)

    parse_mock = mocker.patch(
        "app.etl_pipeline.parsers.vision_llm.parse_image_for_description",
        new=AsyncMock(return_value="Logo desc"),
    )

    fake_llm = MagicMock()
    result = await describe_pictures(str(pdf_file), "report.pdf", fake_llm)

    assert len(result.descriptions) == 1
    assert result.skipped_duplicate == 2
    assert parse_mock.await_count == 1


async def test_describe_pictures_skips_too_small_images(tmp_path, mocker):
    """Sub-1KB images (tracking pixels, dots, etc.) are skipped."""
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    tiny = _make_image_obj("dot.png", b"\x89PNG\r\n\x1a\n")
    big = _make_image_obj("ct.jpeg", b"\xff\xd8\xff\xe0" + b"\xab" * 3000)
    page = MagicMock(images=[tiny, big])

    fake_reader = MagicMock()
    fake_reader.pages = [page]
    mocker.patch("pypdf.PdfReader", return_value=fake_reader)

    parse_mock = mocker.patch(
        "app.etl_pipeline.parsers.vision_llm.parse_image_for_description",
        new=AsyncMock(return_value="CT scan"),
    )

    fake_llm = MagicMock()
    result = await describe_pictures(str(pdf_file), "report.pdf", fake_llm)

    assert len(result.descriptions) == 1
    assert result.descriptions[0].name == "ct.jpeg"
    assert result.skipped_too_small == 1
    assert parse_mock.await_count == 1


async def test_describe_pictures_skips_too_large_images(tmp_path, mocker):
    """Images larger than the vision LLM's per-image cap are skipped."""
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    huge = _make_image_obj("huge.jpeg", b"\xff" * (6 * 1024 * 1024))
    ok = _make_image_obj("ok.jpeg", b"\xff\xd8\xff\xe0" + b"\xab" * 2000)
    page = MagicMock(images=[huge, ok])

    fake_reader = MagicMock()
    fake_reader.pages = [page]
    mocker.patch("pypdf.PdfReader", return_value=fake_reader)

    parse_mock = mocker.patch(
        "app.etl_pipeline.parsers.vision_llm.parse_image_for_description",
        new=AsyncMock(return_value="OK image"),
    )

    fake_llm = MagicMock()
    result = await describe_pictures(str(pdf_file), "report.pdf", fake_llm)

    assert len(result.descriptions) == 1
    assert result.descriptions[0].name == "ok.jpeg"
    assert result.skipped_too_large == 1
    assert parse_mock.await_count == 1


async def test_describe_pictures_swallows_per_image_failure(tmp_path, mocker):
    """A vision LLM failure on one image must not kill the whole document."""
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    img_a = _make_image_obj("a.jpeg", b"\xff\xd8" + b"\xab" * 2000)
    img_b = _make_image_obj("b.jpeg", b"\xff\xd8" + b"\xcd" * 2000)
    page = MagicMock(images=[img_a, img_b])

    fake_reader = MagicMock()
    fake_reader.pages = [page]
    mocker.patch("pypdf.PdfReader", return_value=fake_reader)

    mocker.patch(
        "app.etl_pipeline.parsers.vision_llm.parse_image_for_description",
        new=AsyncMock(side_effect=[RuntimeError("vision blew up"), "Success"]),
    )

    fake_llm = MagicMock()
    result = await describe_pictures(str(pdf_file), "report.pdf", fake_llm)

    assert len(result.descriptions) == 1
    assert result.descriptions[0].description == "Success"
    assert result.failed == 1


async def test_describe_pictures_handles_pypdf_open_failure(tmp_path, mocker):
    """A malformed PDF that pypdf can't open returns an empty result."""
    pdf_file = tmp_path / "broken.pdf"
    pdf_file.write_bytes(b"not a pdf")

    mocker.patch("pypdf.PdfReader", side_effect=ValueError("EOF marker not found"))

    fake_llm = MagicMock()
    result = await describe_pictures(str(pdf_file), "broken.pdf", fake_llm)
    assert result.descriptions == []


# ---------------------------------------------------------------------------
# inject_descriptions_inline: replacement patterns
# ---------------------------------------------------------------------------


def _desc(name="Im0", description="A CT scan."):
    return PictureDescription(
        page_number=1,
        ordinal_in_page=0,
        name=name,
        sha256="aa",
        description=description,
    )


def test_inject_no_op_when_no_descriptions():
    markdown = "# Title\n\nbody text\n"
    result = PictureExtractionResult()
    out, n = inject_descriptions_inline(markdown, result)
    assert out == markdown
    assert n == 0


def test_inject_replaces_placeholder_with_caption():
    """`<!-- image -->` + `Image: <name>` together becomes one block.

    This is the most common medxpertqa case: our renderer puts a caption
    line right below the embedded JPEG, and Docling preserves both.
    """
    markdown = (
        "# Case\n\n"
        "Clinical text...\n\n"
        "<!-- image -->\nImage: MM-130-a.jpeg\n\n"
        "Answer choices: A) ...\n"
    )
    result = PictureExtractionResult(descriptions=[_desc(name="Im0")])

    out, n = inject_descriptions_inline(markdown, result)

    assert n == 1
    assert "<!-- image -->" not in out
    assert "Image: MM-130-a.jpeg" not in out  # caption consumed
    # New format: horizontal-rule-delimited section with "Embedded
    # image:" anchor and named "Visual description:" section. No
    # blockquote wrapping -- nested blocks (lists, code, tables) inside
    # a blockquote are silently dropped by Streamdown / remark.
    assert "**Embedded image:** `MM-130-a.jpeg`" in out
    assert "**Visual description:**" in out
    assert "A CT scan." in out
    # Block is delimited by horizontal rules so it stands out from
    # surrounding paragraphs.
    assert "\n---\n" in out
    # No OCR section -- this fixture has no ocr_text on its descriptions.
    assert "**OCR text:**" not in out
    # No raw HTML tags / blockquote prefixes leak.
    assert "<image" not in out
    assert "</image>" not in out
    assert "> **Embedded image:**" not in out  # we no longer wrap in `>`
    # Surrounding context is preserved.
    assert "Clinical text..." in out
    assert "Answer choices: A) ..." in out


def test_inject_uses_pypdf_name_when_no_caption():
    """`<!-- image -->` alone uses the pypdf-given name as the attribute."""
    markdown = "# Case\n\n<!-- image -->\n\nMore text\n"
    result = PictureExtractionResult(descriptions=[_desc(name="Im0")])

    out, n = inject_descriptions_inline(markdown, result)

    assert n == 1
    assert "**Embedded image:** `Im0`" in out


def test_inject_replaces_bare_caption():
    """A bare `Image: <name>` line (no placeholder) still gets replaced."""
    markdown = "# Case\n\nText...\nImage: scan.jpeg\nMore text\n"
    result = PictureExtractionResult(descriptions=[_desc(name="Im0")])

    out, n = inject_descriptions_inline(markdown, result)

    assert n == 1
    assert "**Embedded image:** `scan.jpeg`" in out
    assert "Image: scan.jpeg" not in out


def test_inject_handles_multiple_images_in_order():
    """Two placeholders + two descriptions: each consumed in document order."""
    markdown = (
        "Page 1\n\n<!-- image -->\nImage: a.jpeg\n\n"
        "Between\n\n<!-- image -->\nImage: b.jpeg\n\nEnd\n"
    )
    result = PictureExtractionResult(
        descriptions=[
            PictureDescription(
                page_number=1, ordinal_in_page=0, name="Im0", sha256="aa",
                description="Desc A",
            ),
            PictureDescription(
                page_number=2, ordinal_in_page=0, name="Im1", sha256="bb",
                description="Desc B",
            ),
        ]
    )

    out, n = inject_descriptions_inline(markdown, result)

    assert n == 2
    assert "**Embedded image:** `a.jpeg`" in out
    assert "**Embedded image:** `b.jpeg`" in out
    assert out.index("a.jpeg") < out.index("b.jpeg")
    assert "Desc A" in out and "Desc B" in out


def test_inject_returns_remaining_count_when_more_descriptions_than_markers():
    """Three descriptions, one marker -> only one inlined, two leftover."""
    markdown = "Just one <!-- image --> here.\n"
    result = PictureExtractionResult(
        descriptions=[
            _desc(name="Im0", description="First"),
            _desc(name="Im1", description="Second"),
            _desc(name="Im2", description="Third"),
        ]
    )

    out, n = inject_descriptions_inline(markdown, result)

    assert n == 1
    assert "**Embedded image:** `Im0`" in out
    assert "**Embedded image:** `Im1`" not in out


def test_inject_returns_zero_when_no_markers_present():
    """Markdown with no image markers at all returns the input unchanged."""
    markdown = "# Title\n\nJust text. No images mentioned at all.\n"
    result = PictureExtractionResult(descriptions=[_desc(name="Im0")])

    out, n = inject_descriptions_inline(markdown, result)

    assert n == 0
    assert out == markdown


# ---------------------------------------------------------------------------
# render_appended_section
# ---------------------------------------------------------------------------


def test_render_appended_empty_when_nothing_passed():
    assert render_appended_section([]) == ""


def test_render_appended_renders_each_image_as_block():
    descriptions = [
        _desc(name="MM-130-a.jpeg", description="CT scan"),
        _desc(name="MM-130-b.jpeg", description="Bar chart"),
    ]
    rendered = render_appended_section(descriptions)
    assert "## Image Content (vision-LLM extracted)" in rendered
    assert "**Embedded image:** `MM-130-a.jpeg`" in rendered
    assert "CT scan" in rendered
    assert "**Embedded image:** `MM-130-b.jpeg`" in rendered
    assert "Bar chart" in rendered
    # Each image block is delimited by horizontal rules.
    assert rendered.count("\n---\n") >= 2
    # No raw HTML / XML / blockquote prefixes.
    assert "<image" not in rendered
    assert "> **Embedded image:**" not in rendered
    assert "**OCR text:**" not in rendered


def test_render_appended_includes_skip_notes():
    descriptions = [_desc()]
    skip_result = PictureExtractionResult(
        descriptions=descriptions,
        skipped_too_small=2,
        skipped_too_large=1,
        skipped_duplicate=3,
        failed=1,
    )
    rendered = render_appended_section(descriptions, skip_notes=skip_result)
    assert "_Note:" in rendered
    assert "2 too small" in rendered
    assert "1 too large" in rendered
    assert "3 duplicate" in rendered
    assert "1 failed" in rendered


# ---------------------------------------------------------------------------
# merge_descriptions_into_markdown: top-level
# ---------------------------------------------------------------------------


def test_merge_inlines_when_marker_present():
    markdown = "Text...\n\n<!-- image -->\nImage: scan.jpeg\n\nMore text\n"
    result = PictureExtractionResult(descriptions=[_desc(name="Im0")])

    out = merge_descriptions_into_markdown(markdown, result)

    assert "**Embedded image:** `scan.jpeg`" in out
    # Nothing leaked into an appended section -- we should NOT see the
    # appended-section heading because everything went inline.
    assert "## Image Content" not in out


def test_merge_appends_when_no_marker_present():
    """Zero markers means everything goes into an appended section."""
    markdown = "Pure text doc, no image markers.\n"
    result = PictureExtractionResult(
        descriptions=[_desc(name="Im0", description="An image desc.")]
    )

    out = merge_descriptions_into_markdown(markdown, result)

    assert "Pure text doc" in out
    assert "## Image Content (vision-LLM extracted)" in out
    assert "**Embedded image:** `Im0`" in out


def test_merge_appends_leftovers_with_distinct_heading():
    """One marker, two descriptions -> one inline, second appended under
    a heading that signals it's a leftover.
    """
    markdown = "Text\n\n<!-- image -->\nImage: a.jpeg\n\nEnd\n"
    result = PictureExtractionResult(
        descriptions=[
            _desc(name="Im0", description="First"),
            _desc(name="Im1", description="Second"),
        ]
    )

    out = merge_descriptions_into_markdown(markdown, result)

    assert "**Embedded image:** `a.jpeg`" in out  # inlined
    assert "## Image Content (additional, no inline marker found)" in out
    assert "**Embedded image:** `Im1`" in out  # appended


# ---------------------------------------------------------------------------
# describe_pictures: ocr_runner integration
#
# These tests cover the per-image OCR side-channel: when the caller
# supplies an ``ocr_runner`` callable, each extracted image is sent
# both to the vision LLM (visual description) and to the OCR runner
# (text-in-image), in parallel. The OCR text -- if any -- is recorded
# on the PictureDescription and rendered in the inline block.
# ---------------------------------------------------------------------------


async def test_describe_pictures_calls_ocr_runner_per_image(tmp_path, mocker):
    """When an ocr_runner is provided, it's invoked once per eligible image."""
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    img_a = _make_image_obj("Im0.jpeg", b"\xff\xd8\xff\xe0" + b"\xab" * 2000)
    img_b = _make_image_obj("Im1.png", b"\x89PNG\r\n\x1a\n" + b"\xcd" * 2000)
    fake_reader = MagicMock()
    fake_reader.pages = [MagicMock(images=[img_a, img_b])]
    mocker.patch("pypdf.PdfReader", return_value=fake_reader)

    mocker.patch(
        "app.etl_pipeline.parsers.vision_llm.parse_image_for_description",
        new=AsyncMock(side_effect=["Visual A", "Visual B"]),
    )
    ocr_runner = AsyncMock(side_effect=["OCR text A", "OCR text B"])

    fake_llm = MagicMock()
    result = await describe_pictures(
        str(pdf_file), "report.pdf", fake_llm, ocr_runner=ocr_runner
    )

    assert ocr_runner.await_count == 2
    by_name = {d.name: d.ocr_text for d in result.descriptions}
    assert by_name == {"Im0.jpeg": "OCR text A", "Im1.png": "OCR text B"}


async def test_describe_pictures_runs_vision_and_ocr_in_parallel(
    tmp_path, mocker
):
    """Vision LLM and OCR run concurrently per image, not sequentially.

    We verify this by recording call timestamps: if both finish within
    a small window relative to the per-call sleep, they ran in parallel.
    """
    import asyncio
    import time

    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    img = _make_image_obj("Im0.jpeg", b"\xff\xd8\xff\xe0" + b"\xab" * 2000)
    fake_reader = MagicMock()
    fake_reader.pages = [MagicMock(images=[img])]
    mocker.patch("pypdf.PdfReader", return_value=fake_reader)

    sleep_each = 0.05  # 50ms per call

    async def slow_vision(*args, **kwargs):
        await asyncio.sleep(sleep_each)
        return "Visual"

    async def slow_ocr(*args, **kwargs):
        await asyncio.sleep(sleep_each)
        return "OCR"

    mocker.patch(
        "app.etl_pipeline.parsers.vision_llm.parse_image_for_description",
        new=slow_vision,
    )

    fake_llm = MagicMock()
    started = time.perf_counter()
    result = await describe_pictures(
        str(pdf_file), "report.pdf", fake_llm, ocr_runner=slow_ocr
    )
    elapsed = time.perf_counter() - started

    assert len(result.descriptions) == 1
    assert result.descriptions[0].ocr_text == "OCR"
    # Sequential would be ~2*sleep_each. Parallel is ~1*sleep_each + overhead.
    # Be generous with the bound so we're not flaky on slow CI.
    assert elapsed < 1.5 * sleep_each, (
        f"vision+OCR appear to be sequential (took {elapsed:.3f}s)"
    )


async def test_describe_pictures_treats_empty_ocr_as_none(tmp_path, mocker):
    """Empty / whitespace-only OCR result is normalised to None.

    This means the rendered image block won't carry an empty
    "OCR text" section for images that contain no text at all
    (e.g. a clean radiograph).
    """
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    img = _make_image_obj("scan.jpeg", b"\xff\xd8\xff\xe0" + b"\xab" * 2000)
    fake_reader = MagicMock()
    fake_reader.pages = [MagicMock(images=[img])]
    mocker.patch("pypdf.PdfReader", return_value=fake_reader)

    mocker.patch(
        "app.etl_pipeline.parsers.vision_llm.parse_image_for_description",
        new=AsyncMock(return_value="A radiograph."),
    )
    ocr_runner = AsyncMock(return_value="   \n  \n")

    fake_llm = MagicMock()
    result = await describe_pictures(
        str(pdf_file), "report.pdf", fake_llm, ocr_runner=ocr_runner
    )

    assert len(result.descriptions) == 1
    assert result.descriptions[0].ocr_text is None


async def test_describe_pictures_swallows_ocr_runner_failure(tmp_path, mocker):
    """An OCR runner exception must not kill the description for that image.

    OCR is supplementary; the vision LLM's description is the primary
    payload. If OCR blows up we drop the OCR field for that image and
    keep the description.
    """
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    img = _make_image_obj("scan.jpeg", b"\xff\xd8\xff\xe0" + b"\xab" * 2000)
    fake_reader = MagicMock()
    fake_reader.pages = [MagicMock(images=[img])]
    mocker.patch("pypdf.PdfReader", return_value=fake_reader)

    mocker.patch(
        "app.etl_pipeline.parsers.vision_llm.parse_image_for_description",
        new=AsyncMock(return_value="A radiograph."),
    )
    ocr_runner = AsyncMock(side_effect=RuntimeError("OCR backend down"))

    fake_llm = MagicMock()
    result = await describe_pictures(
        str(pdf_file), "report.pdf", fake_llm, ocr_runner=ocr_runner
    )

    assert len(result.descriptions) == 1
    assert result.descriptions[0].description == "A radiograph."
    assert result.descriptions[0].ocr_text is None
    assert result.failed == 0  # the IMAGE didn't fail; only its OCR did


async def test_describe_pictures_vision_failure_with_ocr_runner_skips_image(
    tmp_path, mocker
):
    """If the vision LLM fails, the image is skipped even if OCR succeeded.

    The inline block's primary purpose is the visual description; an
    OCR-only block would be misleading (it'd look like the vision
    pipeline ran when it didn't), so we treat vision failure as image
    failure regardless of OCR outcome.
    """
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    img = _make_image_obj("scan.jpeg", b"\xff\xd8\xff\xe0" + b"\xab" * 2000)
    fake_reader = MagicMock()
    fake_reader.pages = [MagicMock(images=[img])]
    mocker.patch("pypdf.PdfReader", return_value=fake_reader)

    mocker.patch(
        "app.etl_pipeline.parsers.vision_llm.parse_image_for_description",
        new=AsyncMock(side_effect=RuntimeError("vision blew up")),
    )
    ocr_runner = AsyncMock(return_value="OCR text")

    fake_llm = MagicMock()
    result = await describe_pictures(
        str(pdf_file), "report.pdf", fake_llm, ocr_runner=ocr_runner
    )

    assert result.descriptions == []
    assert result.failed == 1


async def test_describe_pictures_no_ocr_runner_keeps_ocr_text_none(
    tmp_path, mocker
):
    """Backward compat: omitting ocr_runner produces description-only blocks."""
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    img = _make_image_obj("Im0.jpeg", b"\xff\xd8\xff\xe0" + b"\xab" * 2000)
    fake_reader = MagicMock()
    fake_reader.pages = [MagicMock(images=[img])]
    mocker.patch("pypdf.PdfReader", return_value=fake_reader)

    mocker.patch(
        "app.etl_pipeline.parsers.vision_llm.parse_image_for_description",
        new=AsyncMock(return_value="Visual"),
    )

    fake_llm = MagicMock()
    result = await describe_pictures(str(pdf_file), "report.pdf", fake_llm)

    assert len(result.descriptions) == 1
    assert result.descriptions[0].ocr_text is None


# ---------------------------------------------------------------------------
# Rendering: "OCR text" section appears iff PictureDescription.ocr_text is set
# ---------------------------------------------------------------------------


def _desc_with_ocr(name="Im0", description="A CT scan.", ocr_text="L  R  10mm"):
    return PictureDescription(
        page_number=1,
        ordinal_in_page=0,
        name=name,
        sha256="aa",
        description=description,
        ocr_text=ocr_text,
    )


def test_inject_renders_ocr_section_when_ocr_text_present():
    markdown = "Text\n\n<!-- image -->\nImage: scan.jpeg\n\nMore\n"
    result = PictureExtractionResult(
        descriptions=[_desc_with_ocr(name="Im0", ocr_text="L  R  10mm")]
    )

    out, n = inject_descriptions_inline(markdown, result)

    assert n == 1
    assert "**Embedded image:** `scan.jpeg`" in out
    assert "**OCR text:**" in out
    assert "L  R  10mm" in out
    # OCR section comes before the visual description (literal text
    # first, interpretation second).
    assert out.index("**OCR text:**") < out.index("**Visual description:**")
    # Critical: no nested-block constructs (fenced code, blockquote)
    # that previous formats relied on -- both broke in Streamdown /
    # PlateJS by escaping their container and dropping content.
    assert "```" not in out
    assert "> **" not in out


def test_inject_renders_multiline_ocr_with_hard_breaks():
    """Multi-line OCR uses trailing-two-spaces hard breaks so each
    line renders on its own row, without needing a fragile fenced
    code block or blockquote wrapper."""
    markdown = "Text\n\n<!-- image -->\nImage: scan.jpeg\n\nMore\n"
    ocr_multi = "Slice 24 / 60\nL\nR\n10 mm"
    result = PictureExtractionResult(
        descriptions=[_desc_with_ocr(name="Im0", ocr_text=ocr_multi)]
    )

    out, _ = inject_descriptions_inline(markdown, result)

    # Every OCR line is present.
    for line in ("Slice 24 / 60", "L", "R", "10 mm"):
        assert line in out
    # Non-last OCR lines get the trailing two-space hard break.
    assert "Slice 24 / 60  \n" in out
    assert "\nL  \n" in out
    assert "\nR  \n" in out
    # Last OCR line must NOT carry the two-space hard break (no stray <br>).
    assert "10 mm  \n" not in out
    assert "10 mm\n" in out


def test_render_appended_renders_ocr_section_when_ocr_text_present():
    descriptions = [
        _desc_with_ocr(
            name="MM-130-a.jpeg",
            description="Axial CT.",
            ocr_text="Slice 24 / 60",
        ),
    ]
    rendered = render_appended_section(descriptions)

    assert "**OCR text:**" in rendered
    assert "Slice 24 / 60" in rendered
    assert "Axial CT." in rendered


def test_render_omits_ocr_section_when_ocr_text_is_none():
    descriptions = [_desc(name="Im0", description="A clean radiograph.")]
    rendered = render_appended_section(descriptions)

    assert "**Embedded image:** `Im0`" in rendered
    assert "**OCR text:**" not in rendered
    assert "**Visual description:**" in rendered
    # No raw HTML / blockquote prefixes.
    assert "<image" not in rendered
    assert "> **" not in rendered


# ---------------------------------------------------------------------------
# inject_descriptions_inline: <figure> blocks (layout-aware parsers)
#
# Azure Document Intelligence's ``prebuilt-layout`` and LlamaCloud
# premium both emit ``<figure>...</figure>`` blocks that already contain
# the parser's own OCR of the figure (chart bar values, axis labels,
# inline ``<figcaption>``, embedded ``<table>`` for tabular figures).
# That parser-side content is useful for retrieval on its own, so we
# PRESERVE the figure verbatim and append our vision-LLM block
# immediately after rather than substituting for it.
# ---------------------------------------------------------------------------


def test_inject_appends_block_after_figure_preserving_parser_content():
    """Figure block stays intact; vision-LLM block goes right after it."""
    markdown = (
        "Some narrative text.\n\n"
        "<figure>\n\n"
        "Republican\n68\nDemocrat\n30\n"
        "\n</figure>\n\n"
        "Following paragraph.\n"
    )
    result = PictureExtractionResult(
        descriptions=[_desc(name="Im0", description="Bar chart of party ID.")]
    )

    out, n = inject_descriptions_inline(markdown, result)

    assert n == 1
    # Original figure is preserved verbatim -- the parser's OCR'd
    # numbers must still be searchable.
    assert "<figure>" in out
    assert "</figure>" in out
    assert "Republican" in out and "68" in out
    # Our vision-LLM block follows the figure, not before / inside it.
    assert "**Embedded image:** `Im0`" in out
    assert "Bar chart of party ID." in out
    figure_close = out.index("</figure>")
    embedded_at = out.index("**Embedded image:** `Im0`")
    assert figure_close < embedded_at, "block must be appended AFTER </figure>"
    # Surrounding narrative is preserved.
    assert "Some narrative text." in out
    assert "Following paragraph." in out


def test_inject_handles_multiple_figures_in_document_order():
    """N figures + N descriptions: each pair lands in the right place."""
    markdown = (
        "Page 1\n\n<figure>\nChart A bars\n</figure>\n\n"
        "Between\n\n<figure>\nChart B bars\n</figure>\n\n"
        "End.\n"
    )
    result = PictureExtractionResult(
        descriptions=[
            PictureDescription(
                page_number=1, ordinal_in_page=0, name="Im0", sha256="aa",
                description="Description of chart A.",
            ),
            PictureDescription(
                page_number=2, ordinal_in_page=0, name="Im1", sha256="bb",
                description="Description of chart B.",
            ),
        ]
    )

    out, n = inject_descriptions_inline(markdown, result)

    assert n == 2
    # Both figures preserved; both descriptions inlined; order matches.
    assert out.count("<figure>") == 2
    assert out.count("</figure>") == 2
    assert "Description of chart A." in out
    assert "Description of chart B." in out
    assert out.index("Description of chart A.") < out.index(
        "Description of chart B."
    )
    # Each description appears AFTER its corresponding </figure>.
    first_close = out.index("</figure>")
    assert first_close < out.index("Description of chart A.")
    second_close = out.index("</figure>", first_close + 1)
    assert second_close < out.index("Description of chart B.")


def test_inject_figures_with_attributes_and_nested_tags():
    """``<figure>`` with attributes and nested tags is matched and preserved."""
    markdown = (
        '<figure id="fig-3" class="chart">\n'
        '<figcaption>Source: Pew Research</figcaption>\n'
        "<table><tr><td>Republican</td><td>57</td></tr></table>\n"
        "</figure>\n"
    )
    result = PictureExtractionResult(
        descriptions=[_desc(name="Im0", description="Survey table.")]
    )

    out, n = inject_descriptions_inline(markdown, result)

    assert n == 1
    # All nested HTML is preserved (chunking will pick it up).
    assert 'id="fig-3"' in out
    assert "<figcaption>Source: Pew Research</figcaption>" in out
    assert "<table>" in out and "Republican" in out and "57" in out
    # Our block sits after the closing tag.
    assert out.index("</figure>") < out.index("**Embedded image:** `Im0`")


def test_inject_figures_more_descriptions_than_figures_returns_remaining():
    """Three descriptions, one figure -> one inlined, two left for caller."""
    markdown = "Text.\n<figure>\nbar values\n</figure>\nMore.\n"
    result = PictureExtractionResult(
        descriptions=[
            _desc(name="Im0", description="First desc."),
            _desc(name="Im1", description="Second desc."),
            _desc(name="Im2", description="Third desc."),
        ]
    )

    out, n = inject_descriptions_inline(markdown, result)

    assert n == 1
    assert "First desc." in out
    # Leftovers are the caller's job; inject_descriptions_inline does
    # not append them on its own.
    assert "Second desc." not in out
    assert "Third desc." not in out


def test_inject_figures_more_figures_than_descriptions_leaves_extras_untouched():
    """Two figures, one description -> first figure enriched, second left raw."""
    markdown = (
        "<figure>\nfigure 1 content\n</figure>\n"
        "<figure>\nfigure 2 content\n</figure>\n"
    )
    result = PictureExtractionResult(
        descriptions=[_desc(name="Im0", description="Only description.")]
    )

    out, n = inject_descriptions_inline(markdown, result)

    assert n == 1
    # Both figures still present; only the first one was enriched.
    assert out.count("<figure>") == 2
    assert "Only description." in out
    # Second figure has no embedded-image block immediately after it.
    second_open = out.index("<figure>", out.index("<figure>") + 1)
    second_close = out.index("</figure>", second_open)
    after_second = out[second_close:]
    assert "**Embedded image:**" not in after_second


def test_merge_inlines_at_figure_boundary():
    """Top-level helper does the right thing with figures (no leftover section)."""
    markdown = "Lead.\n<figure>\nbars\n</figure>\nTrailer.\n"
    result = PictureExtractionResult(
        descriptions=[_desc(name="Im0", description="Bar chart.")]
    )

    out = merge_descriptions_into_markdown(markdown, result)

    # Inline succeeded -> no appended-section heading.
    assert "## Image Content" not in out
    assert "Bar chart." in out
    assert "<figure>" in out and "</figure>" in out


def test_inject_figures_then_falls_through_to_docling_marker():
    """Mixed-marker doc: figure consumed first, then Docling placeholder.

    Defensive -- single docs are usually one parser's output, but if a
    pipeline ever stitches two parsers' markdowns together the inliner
    should still place each description.
    """
    markdown = (
        "<figure>\nChart bars: 50, 40, 30\n</figure>\n\n"
        "Later in the doc:\n\n"
        "<!-- image -->\nImage: scan.jpeg\n\n"
        "End.\n"
    )
    result = PictureExtractionResult(
        descriptions=[
            _desc(name="Im0", description="Chart description."),
            _desc(name="Im1", description="Scan description."),
        ]
    )

    out, n = inject_descriptions_inline(markdown, result)

    assert n == 2
    # Figure preserved + augmented.
    assert "<figure>" in out and "Chart bars: 50, 40, 30" in out
    assert "Chart description." in out
    # Docling placeholder + caption replaced.
    assert "<!-- image -->" not in out
    assert "Image: scan.jpeg" not in out
    assert "**Embedded image:** `scan.jpeg`" in out
    assert "Scan description." in out
