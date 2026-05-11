"""Stub DoclingService.process_document for E2E.

The real ``DoclingService.process_document`` calls
``DocumentConverter.convert(file_path)`` which lazily downloads the
``docling-project/docling-layout-heron`` model from Hugging Face Hub.
The hermetic E2E container sets ``HF_HUB_OFFLINE=1`` (see
``docker/docker-compose.e2e.yml``), so that download fails with
``LocalEntryNotFoundError`` and the indexing Celery task retries until
the Playwright test hits its ~4-minute step timeout. In CI that is the
difference between the suite finishing and the 30-minute job timeout
killing the run before any report can upload.

Stubbing ``process_document`` bypasses ``DocumentConverter.convert()``
entirely. ``DoclingService.__init__`` is intentionally left untouched
because constructing ``DocumentConverter(...)`` is cheap and offline —
it is only ``.convert()`` that triggers the offline-model download.

Every canary PDF under ``tests/e2e/fakes/fixtures/binary/`` is produced
by ``generate_canary_pdfs.py`` and embeds its canary token as plain
``(text) Tj`` PDF text operators. Extracting those operators gives us
the canary string back, which is what the Playwright assertions look
for in the resulting Document row.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Matches the `(escaped text) Tj` text-show operator emitted by
# generate_canary_pdfs.py. Inside the parens, the escape rules are:
#   \\  -> backslash
#   \(  -> literal (
#   \)  -> literal )
# The character class [^\\()] consumes any non-escape byte; \\. consumes
# an escape sequence. Sufficient for our synthetic fixtures.
_TJ_PATTERN = re.compile(rb"\(((?:[^\\()]|\\.)*)\)\s*Tj")


def _extract_text_from_synthetic_pdf(file_path: str) -> str:
    """Pull every ``(text) Tj`` payload out of a fixture PDF in order.

    Returns an empty string if the file cannot be read. We do not try to
    handle arbitrary PDFs because the fake is only ever invoked against
    fixtures we generate ourselves.
    """
    try:
        data = Path(file_path).read_bytes()
    except OSError as exc:
        logger.warning("[fake-docling] could not read %s: %s", file_path, exc)
        return ""

    lines: list[str] = []
    for match in _TJ_PATTERN.finditer(data):
        raw = match.group(1)
        # Order-sensitive unescape via sentinel: protect `\\` first so
        # the subsequent `\(` / `\)` passes do not corrupt it.
        text = (
            raw.replace(rb"\\", b"\x00")
            .replace(rb"\(", b"(")
            .replace(rb"\)", b")")
            .replace(b"\x00", b"\\")
        )
        try:
            lines.append(text.decode("utf-8"))
        except UnicodeDecodeError:
            lines.append(text.decode("latin-1"))
    return "\n".join(lines)


async def fake_process_document(
    self,
    file_path: str,
    filename: str | None = None,
) -> dict[str, Any]:
    """Drop-in replacement for ``DoclingService.process_document``.

    Returns the same dict shape as the production method so callers
    (``app/etl_pipeline/parsers/docling.py``) can keep reading
    ``result["content"]`` without changes.
    """
    extracted = _extract_text_from_synthetic_pdf(file_path)
    display_name = filename or Path(file_path).name

    if extracted:
        content = f"# {display_name}\n\n{extracted}\n"
    else:
        # Empty fallback so the indexing pipeline does not error out on
        # an unexpected payload. A failing canary assertion is a much
        # clearer failure mode than a hard parser exception.
        content = f"# {display_name}\n\n(empty docling fake — no text-show operators found)\n"

    logger.info(
        "[fake-docling] returning %d chars for %s",
        len(content),
        display_name,
    )

    return {
        "content": content,
        "full_text": content,
        "service_used": "docling-fake",
        "status": "success",
        "processing_notes": "e2e fake DoclingService — no real PDF parsing",
    }


def install(patches: list[Any]) -> None:
    """Patch ``DoclingService.process_document`` at the class level.

    Patching the class method (rather than each call site) is correct
    here because every consumer goes through
    ``create_docling_service()`` → ``DoclingService()`` → instance method
    dispatch, so the descriptor protocol picks up our replacement. There
    is exactly one such consumer today
    (``app/etl_pipeline/parsers/docling.py``), but patching the class is
    future-proof.

    Fails loud rather than warning, because a silent passthrough means
    real Docling + ``HF_HUB_OFFLINE=1`` = 4 minutes of CI hang per test.
    """
    from unittest.mock import patch as _patch

    target = "app.services.docling_service.DoclingService.process_document"
    try:
        p = _patch(target, fake_process_document)
        p.start()
        patches.append(p)
        logger.info("[fake-docling] patched %s", target)
    except (ModuleNotFoundError, AttributeError) as exc:
        raise RuntimeError(
            f"Could not patch Docling binding {target!r}: {exc!s}. "
            f"Update surfsense_backend/tests/e2e/fakes/docling_service.py "
            f"to point at the new binding site."
        ) from exc
