"""Extract embedded images from PDFs, describe them, and inject the
descriptions inline into the parser's markdown.

When the operator passes ``use_vision_llm=True`` for a PDF, the document
parsers (DOCLING / LLAMACLOUD / Azure DI / UNSTRUCTURED) extract text
but mostly drop the actual image content -- a CT scan inside a clinical
PDF becomes (at best) a ``<!-- image -->`` placeholder in the markdown,
and the caption text below it.

This module fills that gap. After the document parser produces markdown
text, we:

1. Walk the original PDF with :mod:`pypdf`, pulling out each embedded
   image (deduped by sha256, size-capped to match the vision LLM's own
   limits).
2. Run the vision LLM on each unique image (visual description) and,
   in parallel when an OCR runner is provided, re-feed the same image
   through the ETL service for per-image OCR.
3. **Inject** a horizontal-rule-delimited markdown section -- with
   named "OCR text" and "Visual description" sub-sections -- where the
   image actually appears in the parser's markdown. Two splice modes,
   chosen by which marker the parser emitted:

   - **Replace** Docling-style ``<!-- image -->`` placeholders (and an
     optional ``Image: <filename>`` caption line). The placeholder
     carries no useful content of its own, so we substitute our block
     for it.
   - **Append after** layout-aware ``<figure>...</figure>`` blocks
     (Azure DI ``prebuilt-layout``, LlamaCloud premium). Those blocks
     already contain parser-extracted chart values / OCR'd labels /
     captions, which are themselves useful for retrieval -- so we
     PRESERVE the figure verbatim and add our vision-LLM block
     immediately after it. The chunk then contains both the parser's
     structured numbers AND the VLM's semantic interpretation.

   Either way, the image content stays in context with the surrounding
   document body rather than getting orphaned at the end -- crucial for
   retrieval, where a single chunk should contain the question, the
   image content, and the answer options together.

If no placeholders, figures, or captions can be matched (e.g. an
unusual parser output), we fall back to appending an
``## Image Content`` section so no image content is silently lost.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import re
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Type alias for the OCR callback. Takes (file_path, filename), returns
# the OCR'd markdown text -- or empty string if no text was found, or
# raises if OCR failed unrecoverably (which the describer catches and
# treats as "no OCR for this image" rather than failing the whole doc).
OcrRunner = Callable[[str, str], Awaitable[str]]

logger = logging.getLogger(__name__)


# Bound how many vision LLM calls we make in parallel for a single
# document. Vision models are typically rate-limited; 4 concurrent
# calls is a safe default that respects most provider limits while
# keeping wall-clock manageable for image-heavy PDFs.
_VISION_CONCURRENCY = 4

# Match parse_with_vision_llm's per-image cap so we don't even attempt
# images that the vision LLM would reject anyway (Anthropic's 5 MB
# limit is the most restrictive among the major providers).
_MAX_IMAGE_BYTES = 5 * 1024 * 1024

# Skip degenerate images: tracking pixels, very small decorative dots,
# scanner-introduced artefacts. We can't cheaply check pixel dimensions
# without decoding the image, so we approximate: anything under 1 KB is
# almost certainly not informative content.
_MIN_IMAGE_BYTES = 1024


@dataclass
class PictureDescription:
    """A single extracted image with its visual description and (optionally) OCR.

    Two content fields by design, each produced by the *right* tool:

    - ``description``: the vision LLM's visual interpretation. What the
      image depicts (anatomy, charts, layout, etc.) -- the semantic
      content that only a vision model can produce.
    - ``ocr_text``: text-in-image extracted by re-feeding the image
      through the configured ETL service (Docling/Azure DI/LlamaCloud)
      *as if it were a standalone image upload*. Specialist OCR engine,
      per-image attribution, no vision LLM tokens spent on text. None
      when no OCR was requested or OCR found no text.
    """

    page_number: int                # 1-indexed
    ordinal_in_page: int            # 0-indexed within the page
    name: str                       # name pypdf assigned (e.g. "Im0")
    sha256: str                     # hash of the raw image bytes
    description: str                # visual description (markdown)
    ocr_text: str | None = None     # OCR text from the ETL service, if any


@dataclass
class PictureExtractionResult:
    """Aggregate result of extracting all pictures from a document."""

    descriptions: list[PictureDescription] = field(default_factory=list)
    skipped_too_small: int = 0
    skipped_too_large: int = 0
    skipped_duplicate: int = 0
    failed: int = 0

    @property
    def has_content(self) -> bool:
        return bool(self.descriptions)


def _is_pdf(filename: str) -> bool:
    return filename.lower().endswith(".pdf")


def _pick_suffix(name: str) -> str:
    lower = name.lower()
    for ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"):
        if lower.endswith(ext):
            return ".jpeg" if ext == ".jpg" else ext
    return ".png"


def _extract_pdf_images(file_path: str) -> list[tuple[int, int, str, bytes]]:
    """Pull every embedded image out of a PDF.

    Returns ``(page_number_1_indexed, ordinal_in_page, name, bytes)``.
    Per-page and per-image failures are logged and skipped -- one bad
    image must not fail the whole document.
    """

    from pypdf import PdfReader

    out: list[tuple[int, int, str, bytes]] = []
    try:
        reader = PdfReader(file_path)
    except Exception:
        logger.warning(
            "pypdf failed to open %s for image extraction",
            file_path,
            exc_info=True,
        )
        return out

    for page_idx, page in enumerate(reader.pages):
        try:
            images = list(page.images)
        except Exception:
            logger.warning(
                "pypdf failed to enumerate images on page %d of %s",
                page_idx + 1,
                file_path,
                exc_info=True,
            )
            continue
        for img_idx, img in enumerate(images):
            try:
                name = getattr(img, "name", None) or f"page{page_idx + 1}_img{img_idx}"
                data = img.data
            except Exception:
                logger.warning(
                    "pypdf failed to read image %d on page %d of %s",
                    img_idx,
                    page_idx + 1,
                    file_path,
                    exc_info=True,
                )
                continue
            out.append((page_idx + 1, img_idx, name, data))
    return out


async def _describe_one(
    page_number: int,
    ordinal: int,
    name: str,
    sha256: str,
    data: bytes,
    vision_llm: Any,
    semaphore: asyncio.Semaphore,
    ocr_runner: OcrRunner | None,
) -> PictureDescription | None:
    from app.etl_pipeline.parsers.vision_llm import parse_image_for_description

    suffix = _pick_suffix(name)
    # NamedTemporaryFile + delete=False because the vision-LLM helper
    # and the OCR runner each open the path themselves; we clean up in
    # the finally. Same temp file feeds both, which is correct: vision
    # LLM and OCR are looking at the same image, just asking different
    # questions of it.
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        async with semaphore:
            tasks: list[Awaitable[Any]] = [
                parse_image_for_description(tmp_path, name, vision_llm),
            ]
            if ocr_runner is not None:
                tasks.append(ocr_runner(tmp_path, name))

            # return_exceptions=True so a failure in one branch (most
            # often OCR) doesn't poison the other.
            results = await asyncio.gather(*tasks, return_exceptions=True)

        description_result = results[0]
        if isinstance(description_result, BaseException):
            logger.warning(
                "Vision LLM failed for image %s on page %d, skipping",
                name,
                page_number,
                exc_info=description_result,
            )
            return None
        description = str(description_result)

        ocr_text: str | None = None
        if ocr_runner is not None and len(results) > 1:
            ocr_result = results[1]
            if isinstance(ocr_result, BaseException):
                logger.warning(
                    "Per-image OCR failed for image %s on page %d, "
                    "omitting OCR field for this image",
                    name,
                    page_number,
                    exc_info=ocr_result,
                )
            else:
                stripped = str(ocr_result).strip()
                # Empty OCR (or whitespace-only) means the OCR engine
                # found no text in this image. Record that as None so
                # the rendered block doesn't include a useless empty tag.
                ocr_text = stripped or None
    finally:
        with contextlib.suppress(OSError):
            Path(tmp_path).unlink()

    return PictureDescription(
        page_number=page_number,
        ordinal_in_page=ordinal,
        name=name,
        sha256=sha256,
        description=description,
        ocr_text=ocr_text,
    )


async def describe_pictures(
    file_path: str,
    filename: str,
    vision_llm: Any,
    *,
    ocr_runner: OcrRunner | None = None,
) -> PictureExtractionResult:
    """Extract embedded images from a document and describe each via vision LLM.

    When ``ocr_runner`` is provided, each image is also passed to it
    (in parallel with the vision LLM) and the returned text is recorded
    in :attr:`PictureDescription.ocr_text`. The runner is typically a
    closure over a vision-LLM-less ``EtlPipelineService`` -- this lets
    the same OCR engine that processes standalone image uploads
    (Docling/Azure DI/LlamaCloud) also process embedded-in-PDF images,
    giving per-image OCR attribution alongside the page-level OCR that
    the parser already does.

    Currently PDF-only. For non-PDF documents this returns an empty
    result and the caller should leave the parser's markdown untouched.
    """

    result = PictureExtractionResult()
    if not _is_pdf(filename) or vision_llm is None:
        return result

    raw_images = _extract_pdf_images(file_path)
    if not raw_images:
        return result

    seen_hashes: set[str] = set()
    eligible: list[tuple[int, int, str, str, bytes]] = []
    for page_number, ordinal, name, data in raw_images:
        if len(data) > _MAX_IMAGE_BYTES:
            result.skipped_too_large += 1
            continue
        if len(data) < _MIN_IMAGE_BYTES:
            result.skipped_too_small += 1
            continue
        sha = hashlib.sha256(data).hexdigest()
        if sha in seen_hashes:
            result.skipped_duplicate += 1
            continue
        seen_hashes.add(sha)
        eligible.append((page_number, ordinal, name, sha, data))

    if not eligible:
        return result

    semaphore = asyncio.Semaphore(_VISION_CONCURRENCY)
    tasks = [
        _describe_one(p, o, n, sha, d, vision_llm, semaphore, ocr_runner)
        for (p, o, n, sha, d) in eligible
    ]
    descriptions = await asyncio.gather(*tasks)
    for desc in descriptions:
        if desc is None:
            result.failed += 1
        else:
            result.descriptions.append(desc)
    return result


# ---------------------------------------------------------------------------
# Rendering: build the per-image markdown block + inject inline.
# ---------------------------------------------------------------------------


def _format_image_block(
    name: str,
    description: str,
    ocr_text: str | None = None,
) -> str:
    """Render the per-image block as a horizontal-rule-delimited section.

    Why no blockquote / no raw HTML / no XML?
    -----------------------------------------
    We tried each in turn and each failed in the document viewer:

    - **Raw HTML / XML** (``<image>...</image>``): unknown elements
      have no render rules in Streamdown or PlateJS, so the content
      survives in the markdown source but is invisible to humans.
    - **Blockquote with nested blocks**: nested fenced code blocks,
      bullet lists, numbered lists, tables -- any *block* element
      inside a ``>``-prefixed blockquote -- gets evicted by Streamdown
      / remark, dropping everything after it onto the document level.
      The vision LLM happily produces bulleted descriptions, so this
      hit the viewer in practice.

    A horizontal-rule-delimited section, by contrast, contains only
    standard top-level markdown -- bold labels and free-form body --
    so the description's native markdown (lists, prose, tables) all
    renders natively in every renderer.

    Layout (OCR section omitted when ``ocr_text`` is None/empty):

        ---

        **Embedded image:** `MM-130-a.jpeg`

        **OCR text:**
        Slice 24 / 60
        L
        R

        **Visual description:**

        - Axial contrast-enhanced CT showing a large cystic mass...
        - Mass effect on the adjacent stomach.

        ---

    Still LLM-friendly: the ``**Embedded image:** `<filename>``` prefix
    is unique and trivially regex-able (``^\\*\\*Embedded image:\\*\\* `(.+?)`$``).

    Returned with leading and trailing blank-line padding so the rules
    never merge with adjacent paragraphs after splicing.
    """

    parts: list[str] = [f"**Embedded image:** `{name}`"]

    if ocr_text and ocr_text.strip():
        # Bold "OCR text:" label with trailing two spaces (=> <br>) so
        # the first OCR line sits directly under the label rather than
        # forcing a paragraph break that some renderers would style
        # differently. Subsequent OCR lines also use trailing two spaces
        # for hard breaks, so multi-line OCR renders line-by-line
        # without needing a (fragile) fenced code block.
        ocr_clean_lines = [
            ln.rstrip() for ln in ocr_text.strip().splitlines() if ln.strip()
        ]
        parts.append("")
        parts.append("**OCR text:**  ")
        for i, raw in enumerate(ocr_clean_lines):
            suffix = "" if i == len(ocr_clean_lines) - 1 else "  "
            parts.append(f"{raw}{suffix}")

    parts.append("")
    parts.append("**Visual description:**")
    parts.append("")
    parts.append(description.strip())

    body = "\n".join(parts)
    # Wrap with blank lines + horizontal rules so the block is clearly
    # delimited from surrounding paragraphs and survives splicing into
    # the middle of any markdown stream.
    return "\n\n---\n\n" + body + "\n\n---\n\n"


# Patterns we'll try to splice into. Each pattern captures the
# original-PDF filename when one is available (group 1).
#
# Replace-style markers (the matched span is substituted with our block
# because it carries no useful content of its own):
#
# 1. Docling's image placeholder followed by an "Image: <filename>"
#    caption line. This is what our medxpertqa renderer produces:
#    reportlab places the JPEG, then a caption, and Docling outputs
#    the placeholder + caption.
# 2. Docling's image placeholder alone (filename unknown -- we fall
#    back to pypdf's name).
# 3. A bare "Image: <filename>" caption line with no preceding
#    placeholder. Rare in practice, but covers parsers that drop the
#    placeholder entirely.
_PLACEHOLDER_WITH_CAPTION = re.compile(
    r"<!--\s*image\s*-->\s*\n\s*Image:\s*(\S+)\s*(?:\n|$)",
    re.IGNORECASE,
)
_PLACEHOLDER_ONLY = re.compile(
    r"<!--\s*image\s*-->",
    re.IGNORECASE,
)
_CAPTION_ONLY = re.compile(
    r"^[ \t]*Image:\s*(\S+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Append-after marker (the matched span is preserved verbatim and our
# block is inserted immediately after it):
#
# 4. ``<figure>...</figure>`` as emitted by layout-aware parsers (Azure
#    Document Intelligence ``prebuilt-layout``, LlamaCloud premium).
#    The figure's own contents -- chart bar values, axis labels,
#    inline ``<figcaption>``, embedded ``<table>`` for tabular figures
#    -- are themselves specialist OCR output, so we keep them and add
#    our vision-LLM block alongside. ``[^>]*`` in the open tag tolerates
#    optional attributes like ``<figure id="...">``; ``re.DOTALL``
#    lets ``.`` cross the newlines inside the block.
_FIGURE_BLOCK = re.compile(
    r"<figure\b[^>]*>.*?</figure>",
    re.DOTALL | re.IGNORECASE,
)


def _replace_one_match(
    markdown: str,
    pattern: re.Pattern[str],
    descriptions: list[PictureDescription],
    desc_idx: int,
) -> tuple[str, int]:
    """Replace the first occurrence of ``pattern`` with the next image block.

    Returns the new markdown and the new ``desc_idx`` (advanced if a
    replacement happened, unchanged otherwise).
    """

    if desc_idx >= len(descriptions):
        return markdown, desc_idx

    match = pattern.search(markdown)
    if not match:
        return markdown, desc_idx

    desc = descriptions[desc_idx]
    captured_name: str | None = None
    if match.groups():
        captured_name = match.group(1)
    name = captured_name or desc.name
    block = _format_image_block(name, desc.description, desc.ocr_text)

    new_markdown = markdown[: match.start()] + block + markdown[match.end():]
    return new_markdown, desc_idx + 1


def _splice_after_figures(
    markdown: str,
    descriptions: list[PictureDescription],
    desc_idx: int,
) -> tuple[str, int]:
    """Append vision-LLM blocks immediately after each ``<figure>...</figure>``.

    Layout-aware parsers (Azure DI ``prebuilt-layout``, LlamaCloud
    premium) wrap each figure / chart / inline table in this tag and
    carry their own OCR of the figure's text content inside it. That
    content is useful on its own, so we keep the original block
    verbatim and add our vision-LLM block right after it -- giving
    retrieval both signals in the same chunk.

    Descriptions are matched to figures in document order (first
    description -> first figure, etc.). All splice points are computed
    upfront with :func:`re.finditer` and applied in REVERSE order so
    earlier offsets stay valid as the markdown grows. Returns the
    advanced ``desc_idx`` for the caller's leftover-handling.
    """

    if desc_idx >= len(descriptions):
        return markdown, desc_idx

    matches = list(_FIGURE_BLOCK.finditer(markdown))
    if not matches:
        return markdown, desc_idx

    n_to_splice = min(len(matches), len(descriptions) - desc_idx)
    if n_to_splice <= 0:
        return markdown, desc_idx

    out = markdown
    # Walk in reverse so each splice's end-offset still points at the
    # right place in the (still-mutating) string.
    for i in range(n_to_splice - 1, -1, -1):
        match = matches[i]
        desc = descriptions[desc_idx + i]
        block = _format_image_block(desc.name, desc.description, desc.ocr_text)
        out = out[: match.end()] + block + out[match.end():]

    return out, desc_idx + n_to_splice


def inject_descriptions_inline(
    markdown: str,
    result: PictureExtractionResult,
) -> tuple[str, int]:
    """Splice per-image markdown blocks into the document at image positions.

    Walks the markdown left-to-right, consuming descriptions in order.
    Tries two splicing strategies, in this order:

    1. **Append-after** for ``<figure>...</figure>`` blocks emitted by
       layout-aware parsers (Azure DI ``prebuilt-layout``, LlamaCloud
       premium). The figure block carries the parser's own OCR of the
       figure -- we preserve it and add our vision-LLM block right
       after.
    2. **Replace** for Docling-style markers, in priority order:

       - ``<!-- image -->`` followed by ``Image: <filename>`` caption,
       - ``<!-- image -->`` placeholder alone,
       - bare ``Image: <filename>`` caption.

    A document typically uses one style or the other (depending on
    which parser produced its markdown), so the two paths don't fight
    each other in practice. When they do co-occur, figures are
    consumed first.

    Returns ``(new_markdown, n_inlined)`` -- the count of descriptions
    that were placed inline. The caller decides what to do with any
    leftover descriptions (typically: append them at the end).
    """

    if not result.descriptions:
        return markdown, 0

    descriptions = result.descriptions
    desc_idx = 0
    out = markdown

    # Step 1: layout-aware figures. One-shot batch -- finds ALL
    # <figure> blocks, splices in document order until we exhaust
    # either side.
    out, desc_idx = _splice_after_figures(out, descriptions, desc_idx)

    # Step 2: Docling-style replacement markers. One match per
    # iteration, so a doc that has both a figure (consumed above) and
    # a Docling placeholder (consumed below) still works.
    while desc_idx < len(descriptions):
        before_idx = desc_idx
        out, desc_idx = _replace_one_match(
            out, _PLACEHOLDER_WITH_CAPTION, descriptions, desc_idx
        )
        if desc_idx > before_idx:
            continue
        out, desc_idx = _replace_one_match(
            out, _PLACEHOLDER_ONLY, descriptions, desc_idx
        )
        if desc_idx > before_idx:
            continue
        out, desc_idx = _replace_one_match(
            out, _CAPTION_ONLY, descriptions, desc_idx
        )
        if desc_idx > before_idx:
            continue
        # No more positions to splice into.
        break

    return out, desc_idx


def render_appended_section(
    descriptions: list[PictureDescription],
    *,
    skip_notes: PictureExtractionResult | None = None,
    heading: str = "## Image Content (vision-LLM extracted)",
) -> str:
    """Render leftover descriptions as an appended section.

    Used as a fallback when not every description could be inlined
    (either because the parser produced no detectable image markers,
    or because there were more extracted images than markers).
    """

    if not descriptions and not skip_notes:
        return ""

    parts: list[str] = ["", heading, ""]
    for desc in descriptions:
        parts.append(
            _format_image_block(desc.name, desc.description, desc.ocr_text)
        )
        parts.append("")

    if skip_notes is not None:
        notes: list[str] = []
        if skip_notes.skipped_too_large:
            notes.append(f"{skip_notes.skipped_too_large} too large (> 5 MB)")
        if skip_notes.skipped_too_small:
            notes.append(f"{skip_notes.skipped_too_small} too small (< 1 KB)")
        if skip_notes.skipped_duplicate:
            notes.append(f"{skip_notes.skipped_duplicate} duplicate")
        if skip_notes.failed:
            notes.append(f"{skip_notes.failed} failed")
        if notes:
            parts.append(f"_Note: {', '.join(notes)} image(s) skipped._")

    return "\n".join(parts)


def merge_descriptions_into_markdown(
    markdown: str,
    result: PictureExtractionResult,
) -> str:
    """Top-level: inline what we can, append what's left over.

    This is the function the ETL pipeline actually calls. It guarantees
    that no successfully-described image is silently dropped: anything
    we can't splice inline gets appended at the end with a heading
    that makes it clear those came from the document but weren't
    location-matched.
    """

    if not result.descriptions:
        return markdown

    new_markdown, n_inlined = inject_descriptions_inline(markdown, result)
    leftover = result.descriptions[n_inlined:]

    if not leftover:
        return new_markdown

    # Distinguish in the heading whether NONE were inlined (parser
    # produced no markers at all) vs SOME (mismatched count).
    heading = (
        "## Image Content (vision-LLM extracted)"
        if n_inlined == 0
        else "## Image Content (additional, no inline marker found)"
    )
    section = render_appended_section(leftover, heading=heading)
    if not section:
        return new_markdown
    return f"{new_markdown.rstrip()}\n\n{section.lstrip()}\n"


__all__ = [
    "PictureDescription",
    "PictureExtractionResult",
    "describe_pictures",
    "inject_descriptions_inline",
    "merge_descriptions_into_markdown",
    "render_appended_section",
]
