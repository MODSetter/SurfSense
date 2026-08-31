"""Structural checks for interactive HTML artifact fragments."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

from .base import StructuralCheckResult

_ALLOWED_FONT_HOSTS = frozenset({"fonts.googleapis.com", "fonts.gstatic.com"})
_CSS_REFERENCE_RE = re.compile(
    r"""(?:@import\s+|url\(\s*)["']?([^"')\s;]+)""",
    re.IGNORECASE,
)


def _is_allowed_reference(value: str) -> bool:
    value = value.strip()
    if not value or value.startswith(("#", "data:")):
        return True
    parsed = urlsplit(value)
    return parsed.scheme == "https" and parsed.hostname in _ALLOWED_FONT_HOSTS


class _FragmentInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.has_markup = False
        self.has_document_wrapper = False
        self.external_references: list[str] = []
        self._in_style = False

    def handle_decl(self, decl: str) -> None:
        self.has_markup = True
        if decl.lstrip().lower().startswith("doctype"):
            self.has_document_wrapper = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.has_markup = True
        lowered_tag = tag.lower()
        if lowered_tag in {"html", "head", "body"}:
            self.has_document_wrapper = True
        self._in_style = lowered_tag == "style"
        for name, value in attrs:
            if value is None:
                continue
            if name.lower() in {"src", "href"} and not _is_allowed_reference(value):
                self.external_references.append(value.strip())
            elif name.lower() == "style":
                self._inspect_css(value)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self._in_style = False

    def handle_endtag(self, tag: str) -> None:
        lowered_tag = tag.lower()
        if lowered_tag in {"html", "head", "body"}:
            self.has_document_wrapper = True
        if lowered_tag == "style":
            self._in_style = False

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self._inspect_css(data)

    def _inspect_css(self, css: str) -> None:
        for match in _CSS_REFERENCE_RE.finditer(css):
            reference = match.group(1)
            if not _is_allowed_reference(reference):
                self.external_references.append(reference)


def check_html(data: bytes) -> StructuralCheckResult:
    if not data:
        return StructuralCheckResult(("HTML artifact is empty",))

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return StructuralCheckResult(("HTML artifact must be UTF-8 encoded",))

    if not text.strip():
        return StructuralCheckResult(("HTML artifact is empty",))

    inspector = _FragmentInspector()
    try:
        inspector.feed(text)
        inspector.close()
    except (AssertionError, ValueError) as exc:
        return StructuralCheckResult((f"HTML artifact could not be parsed: {exc}",))

    findings: list[str] = []
    if not inspector.has_markup:
        findings.append("HTML artifact contains no markup")
    if inspector.has_document_wrapper:
        findings.append(
            "HTML artifact must be a fragment without doctype, html, head, or body tags"
        )

    notes = tuple(
        f"External resource will be blocked by the artifact viewer: {reference}"
        for reference in dict.fromkeys(inspector.external_references)
    )
    return StructuralCheckResult(tuple(findings), notes=notes)
