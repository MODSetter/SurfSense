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

logger = logging.getLogger(__name__)

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_APP_DATA_RE = re.compile(r'<script id="__APP_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


def extract_next_data(html: str | None) -> dict[str, Any] | None:
    """Return the parsed Next.js state object, or ``None`` when absent/invalid.

    Tries ``__NEXT_DATA__`` first, then the ``__APP_DATA__`` fallback so a single
    Walmart layout experiment does not blank the whole extractor.
    """
    if not html:
        return None
    for pattern in (_NEXT_DATA_RE, _APP_DATA_RE):
        match = pattern.search(html)
        if not match:
            continue
        try:
            data = json.loads(match.group(1))
        except (ValueError, TypeError):
            logger.warning("Walmart hidden JSON present but did not parse")
            continue
        if isinstance(data, dict):
            return data
    return None


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
