"""A page's main text as markdown, and its title, as Web Crawl kept them."""

from typing import Any

import trafilatura
from trafilatura.utils import load_html

from modules.documents.web_sources.page_reading.challenge_walls import is_wall
from modules.documents.web_sources.page_reading.lost_prices import with_prices
from modules.documents.web_sources.pullers.puller import Pulled

# A page that ships this much HTML and yields this little text is a shell its
# scripts fill in, which only a browser reads (Web Crawl's calibration: true
# shells were 3.4 MB or more with under 0.05% text; healthy pages under 650 KB).
_SHELL_MIN_HTML = 1_000_000
_SHELL_MAX_TEXT = 2_500

# Sphinx, MkDocs and anchor.js permalinks: a pilcrow glued onto every heading.
_PERMALINKS = (
    "//a[contains(concat(' ', normalize-space(@class), ' '), ' headerlink ')]"
    " | //a[contains(concat(' ', normalize-space(@class), ' '), ' anchorjs-link ')]"
    " | //a[@aria-hidden='true'][starts-with(@href, '#')]"
)
_PERMALINK_TEXTS = frozenset({"", "¶", "#", "§", "\U0001f517"})


def page_text(html: str, url: str) -> Pulled | None:
    """None when the page holds no text worth keeping: a wall, a shell, nothing at all."""
    tree = load_html(html)
    if tree is None:
        return None
    _strip_permalinks(tree)
    markdown = trafilatura.extract(
        tree,
        url=url,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        include_images=True,
        include_links=True,
    )
    if not markdown or not markdown.strip():
        return None
    markdown = with_prices(tree, html, url, markdown.strip())
    if is_wall(html, markdown):
        return None
    if len(html) >= _SHELL_MIN_HTML and len(markdown) < _SHELL_MAX_TEXT:
        return None
    return Pulled(_title(tree, url), markdown)


def _title(tree: Any, url: str) -> str:
    """The link when the page names none, or its metadata cannot be read."""
    try:
        metadata = trafilatura.extract_metadata(tree, default_url=url)
    except Exception:
        return url
    title = (metadata.title if metadata else None) or ""
    return title.rstrip("¶ ").strip() or url


def _strip_permalinks(tree: Any) -> None:
    for anchor in tree.xpath(_PERMALINKS):
        if anchor.text_content().strip() in _PERMALINK_TEXTS:
            anchor.drop_tree()
