"""What a page asks to load from elsewhere, which its no-network policy blocks (ADR 0066)."""

import re
from html.parser import HTMLParser

# A link is the reader's to follow, not something the page loads.
_LINK_TAGS = frozenset({"a", "area"})
_LOADING_ATTRIBUTES = frozenset({"src", "href", "poster", "data", "srcset"})
# An @import names its address bare, quoted, or wrapped in url(...) like any other.
_CSS_URL = re.compile(
    r"""(?:@import\s+(?:url\(\s*)?|url\(\s*)["']?([^"')\s;]+)""", re.IGNORECASE
)


def _loads(value: str) -> bool:
    value = value.strip()
    return bool(value) and not value.startswith(("data:", "blob:", "#"))


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[str] = []
        self._in_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._in_style = tag == "style"
        for name, value in attrs:
            if value is None:
                continue
            if name == "style":
                self._css(value)
            elif name in _LOADING_ATTRIBUTES and tag not in _LINK_TAGS:
                urls = (
                    [part.split()[0] for part in value.split(",") if part.split()]
                    if name == "srcset"
                    else [value]
                )
                self.found.extend(url.strip() for url in urls if _loads(url))

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self._in_style = False

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self._css(data)

    def _css(self, css: str) -> None:
        self.found.extend(url for url in _CSS_URL.findall(css) if _loads(url))


def outside_resources(page: str) -> list[str]:
    """Each address the page would load, once, in the order it names them."""
    reader = _Reader()
    reader.feed(page)
    reader.close()
    return list(dict.fromkeys(reader.found))
