"""Extract Walmart's hidden Next.js JSON state from page HTML.

Every serious Walmart scraper (Scrapfly, Oxylabs, ScrapeOps, Apify) reads the
``<script id="__NEXT_DATA__">`` JSON blob rather than parsing the rendered DOM,
because Walmart obfuscates CSS classes and A/B-tests layout constantly. The JSON
shape is far more stable across redesigns.

``__APP_DATA__`` is the documented fallback anchor Walmart occasionally ships
instead during layout experiments.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import orjson

logger = logging.getLogger(__name__)

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_APP_DATA_RE = re.compile(r'<script id="__APP_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_SURROGATE_RE = re.compile("[\ud800-\udfff]")


def extract_next_data(html: str | None) -> dict[str, Any] | None:
    """Return the parsed Next.js state object, or ``None`` when absent/invalid.

    Tries ``__NEXT_DATA__`` first, then the ``__APP_DATA__`` fallback so a single
    Walmart layout experiment does not blank the whole extractor. CPU-bound on
    a 1.4 MB search page (orjson keeps it to ~25 ms): call it off the event loop.
    """
    if not html:
        return None
    for pattern in (_NEXT_DATA_RE, _APP_DATA_RE):
        match = pattern.search(html)
        if not match:
            continue
        try:
            data = _loads(match.group(1))
        except (ValueError, TypeError):
            logger.warning("Walmart hidden JSON present but did not parse")
            continue
        if isinstance(data, dict):
            return data
    return None


def _loads(blob: str) -> Any:
    try:
        return orjson.loads(blob)
    except orjson.JSONDecodeError:
        # orjson refuses what json takes, such as a lone surrogate escape in
        # one review's text; that must not lose the page, and the surrogate
        # must not reach the result, which cannot be serialised with it.
        return _mended(json.loads(blob))


def _mended(value: Any) -> Any:
    """``value`` with every lone surrogate replaced by U+FFFD.

    json joins a valid escaped pair into one character, so any surrogate left
    in a string stands alone.
    """
    if isinstance(value, str):
        return _SURROGATE_RE.sub("�", value)
    if isinstance(value, dict):
        return {_mended(key): _mended(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_mended(inner) for inner in value]
    return value


def dig(obj: Any, *keys: str | int) -> Any:
    """Walk nested dict/list keys, returning ``None`` on any miss.

    Tolerates the layout drift between Walmart's ``initialData`` variants without
    a cascade of ``if key in ...`` guards at every call site.
    """
    current = obj
    for key in keys:
        if isinstance(key, int):
            if not isinstance(current, list) or not -len(current) <= key < len(current):
                return None
            current = current[key]
        else:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
    return current


def initial_data(next_data: dict[str, Any]) -> dict[str, Any] | None:
    """The ``props.pageProps.initialData`` node shared by every page type."""
    node = dig(next_data, "props", "pageProps", "initialData")
    return node if isinstance(node, dict) else None
