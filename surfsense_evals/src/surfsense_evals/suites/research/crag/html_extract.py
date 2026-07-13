"""HTML → markdown for CRAG pages, with boilerplate removal.

Each CRAG page is a *full* HTML document (nav, ads, recommended-for-
you, footer, ...). Without removing that boilerplate, retrieval over
the chunks would surface menu items and "subscribe to our newsletter"
boxes instead of the actual page content. We use ``trafilatura``,
which is purpose-built for main-content extraction (the same library
Common Crawl downstream pipelines use). It outputs clean prose with
section headers, lists, and tables preserved.

Extraction policy:
1. ``trafilatura.extract`` with ``output_format="markdown"`` — main
   content only, headers preserved, tables kept.
2. If extraction fails or returns < 200 chars (paywalled / JS-only
   page / extraction confused), fall back to a plain stdlib
   ``HTMLParser`` that strips tags and collapses whitespace. Some
   text is better than no text — SurfSense's chunker handles noisy
   prose.

We *intentionally* keep the page name and URL as visible H1 / link
metadata so the SurfSense chunker preserves doc identity at the top of
the first chunk (mirrors what we do for FRAMES Wikipedia pages).
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser

logger = logging.getLogger(__name__)


_MIN_TRAFILATURA_LENGTH = 200
_MAX_OUTPUT_CHARS = 200_000  # cap to keep upload payloads sane


@dataclass
class ExtractionResult:
    """Outcome of converting one HTML blob to plain markdown."""

    text: str
    method: str          # "trafilatura" | "fallback_strip" | "empty"
    n_chars: int

    @property
    def ok(self) -> bool:
        return self.n_chars > 0


# ---------------------------------------------------------------------------
# Trafilatura wrapper (lazy import so tests / small scripts don't pay)
# ---------------------------------------------------------------------------


def _trafilatura_extract(html_text: str, *, url: str) -> str | None:
    try:
        import trafilatura
    except ImportError:  # pragma: no cover - dependency is required
        logger.warning("trafilatura not installed; falling back to strip-tags only")
        return None
    try:
        text = trafilatura.extract(
            html_text,
            url=url or None,
            output_format="markdown",
            include_links=False,
            include_images=False,
            include_tables=True,
            favor_recall=True,
        )
    except Exception as exc:  # noqa: BLE001 - trafilatura raises a zoo
        logger.debug("trafilatura.extract crashed for %s: %s", url, exc)
        return None
    if not text:
        return None
    return text.strip()


# ---------------------------------------------------------------------------
# Stdlib fallback: strip HTML tags
# ---------------------------------------------------------------------------


class _StripHTMLParser(HTMLParser):
    """Collect text content, treating block tags as paragraph breaks.

    We deliberately drop ``<script>``, ``<style>``, ``<nav>``,
    ``<header>``, ``<footer>``, and ``<aside>`` content — these are
    almost always boilerplate and they are the dominant source of
    noise SurfSense ends up retrieving against if not removed.
    """

    _SKIP_TAGS = frozenset({"script", "style", "nav", "header", "footer", "aside", "svg"})
    _BLOCK_TAGS = frozenset({
        "p", "div", "section", "article", "li", "ul", "ol",
        "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr",
        "td", "th", "table", "blockquote", "pre",
    })

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._buffer: list[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:  # noqa: ARG002
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        if tag in self._BLOCK_TAGS:
            self._buffer.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag in self._BLOCK_TAGS:
            self._buffer.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._buffer.append(data)

    def get_text(self) -> str:
        text = "".join(self._buffer)
        # Decode any leftover entities and collapse whitespace.
        text = html.unescape(text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def _strip_tags(html_text: str) -> str:
    parser = _StripHTMLParser()
    try:
        parser.feed(html_text)
    except Exception as exc:  # noqa: BLE001 - HTMLParser is fragile on garbage input
        logger.debug("HTMLParser failed; using regex strip: %s", exc)
        no_tags = re.sub(r"<[^>]+>", " ", html_text)
        return re.sub(r"\s+", " ", html.unescape(no_tags)).strip()
    return parser.get_text()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_main_content(
    html_text: str,
    *,
    url: str = "",
    page_name: str = "",
    last_modified: str | None = None,
) -> ExtractionResult:
    """Convert one HTML blob into clean markdown for ingest.

    The returned ``text`` is prefixed with a small metadata header
    (``# {page_name}\\n\\nSource: {url}\\n``) so that:

    * SurfSense's chunker has a stable doc-identity anchor at the top
      of the first chunk (matches what we do for FRAMES Wikipedia).
    * The retrieval-augmented arm sees the URL inline, which the LLM
      can surface as a citation if the prompt asks for one.
    """

    body = ""
    method = "empty"
    if html_text and html_text.strip():
        body = _trafilatura_extract(html_text, url=url) or ""
        if body and len(body) >= _MIN_TRAFILATURA_LENGTH:
            method = "trafilatura"
        else:
            stripped = _strip_tags(html_text)
            # Prefer trafilatura output even if short, but only if it
            # contained any prose at all — empty trafilatura fall-through
            # to the stripped form.
            if body and stripped and len(stripped) > len(body) * 1.5 or not body and stripped:
                body = stripped
                method = "fallback_strip"
            elif body:
                method = "trafilatura"

    body = body.strip()
    if len(body) > _MAX_OUTPUT_CHARS:
        body = body[:_MAX_OUTPUT_CHARS] + "\n\n[...truncated...]"

    if not body:
        return ExtractionResult(text="", method="empty", n_chars=0)

    title_line = (page_name or url or "Untitled").strip()
    header_lines = [f"# {title_line}"]
    if url:
        header_lines.append(f"Source: {url}")
    if last_modified:
        header_lines.append(f"Last modified: {last_modified}")
    final = "\n".join(header_lines) + "\n\n" + body + "\n"
    return ExtractionResult(text=final, method=method, n_chars=len(final))


__all__ = ["ExtractionResult", "extract_main_content"]
