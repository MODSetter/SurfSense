"""Prices trafilatura dropped as boilerplate, recovered from the whole page.

Its main-content detection drops div-grid pricing cards and stat tables (live,
duplicati.com/pricing kept 15% of its visible text, goauthentik.io/pricing none of
its five prices). A currency amount is easy to spot, never navigation, and the
point of the pages people ask about, so the repair runs when the visible page shows
one and the markdown kept none: extraction favouring recall, then the whole body as
markdown. One kept amount counts as the prices surviving, so ordinary pages skip a
second extraction.
"""

import re
from copy import deepcopy
from typing import Any

import trafilatura
from lxml import html as lxml_html
from markdownify import markdownify

# $ € £ ¥ ₹ ₩ ₪ ₫ ₴ ₦ ₱ ฿ and ISO codes, before or after the amount ("49€", "USD 49").
_CURRENCY_AMOUNT = re.compile(
    r"[$€£¥₹₩₪₫₴₦₱฿]\s?\d"
    r"|\d\s?[$€£¥₹₩₪₫₴₦₱฿]"
    r"|\b(USD|EUR|GBP|JPY|CNY|INR|BRL|MXN|CAD|AUD|CHF|KRW|SEK|NOK|DKK|PLN)\s?\d"
    r"|\d\s?(USD|EUR|GBP|JPY|CNY|INR|BRL|MXN|CAD|AUD|CHF|KRW|SEK|NOK|DKK|PLN)\b",
    re.IGNORECASE,
)
_NOT_SHOWN = "//script | //style | //noscript | //template | //svg | //iframe | //head"


def with_prices(tree: Any, html: str, url: str, markdown: str) -> str:
    """`markdown`, or a fuller one when it kept none of the page's currency amounts."""
    if not _CURRENCY_AMOUNT.search(html) or _CURRENCY_AMOUNT.search(markdown):
        return markdown
    if not _CURRENCY_AMOUNT.search(_visible_text(tree)):
        return markdown
    recall = trafilatura.extract(
        tree,
        url=url,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        include_images=True,
        include_links=True,
        favor_recall=True,
    )
    if recall and _CURRENCY_AMOUNT.search(recall):
        return recall
    whole = whole_body(tree)
    return whole if whole and _CURRENCY_AMOUNT.search(whole) else markdown


def whole_body(tree: Any) -> str | None:
    """Every visible part of the page as markdown, navigation and footer included."""
    root = _shown_only(tree)
    markdown = markdownify(lxml_html.tostring(root, encoding="unicode"))
    return re.sub(r"\n{3,}", "\n\n", markdown).strip() or None


def _visible_text(tree: Any) -> str:
    return " ".join(" ".join(_shown_only(tree).itertext()).split())


def _shown_only(tree: Any) -> Any:
    """A copy without what a reader never sees; `tree` is left as it was."""
    root = deepcopy(tree)
    for hidden in root.xpath(_NOT_SHOWN):
        parent = hidden.getparent()
        if parent is not None:
            parent.remove(hidden)
    return root
