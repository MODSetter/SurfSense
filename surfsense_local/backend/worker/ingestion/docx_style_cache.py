"""Style lookups remembered while Docling reads one Word file.

Docling asks for a paragraph's style once per run and python-docx scans every
style for each answer: on a long contract that was 80% of a 25 s read.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

# Per block and per thread, so a writer elsewhere never reads a stale style.
_remembered: ContextVar[dict[tuple[Any, ...], Any] | None] = ContextVar(
    "docx_style_lookups", default=None
)
_install_lock = threading.Lock()
_active = 0
_original: Any = None


@contextmanager
def cached_style_lookups() -> Iterator[None]:
    """Within the block, each document part looks a style up once per
    (style_id, style_type); python-docx is as it was once the block ends."""
    _install()
    token = _remembered.set({})
    try:
        yield
    finally:
        _remembered.reset(token)
        _uninstall()


def _install() -> None:
    from docx.parts.document import DocumentPart

    global _active, _original
    with _install_lock:
        if _active == 0:
            _original = DocumentPart.get_style
            DocumentPart.get_style = _get_style
        _active += 1


def _uninstall() -> None:
    from docx.parts.document import DocumentPart

    global _active
    with _install_lock:
        _active -= 1
        if _active == 0:
            DocumentPart.get_style = _original


def _get_style(part: Any, style_id: str | None, style_type: Any) -> Any:
    remembered = _remembered.get()
    if remembered is None:
        # Another thread's python-docx, while a conversion holds the patch.
        return _original(part, style_id, style_type)
    key = (part, style_id, style_type)
    if key not in remembered:
        remembered[key] = _original(part, style_id, style_type)
    return remembered[key]
