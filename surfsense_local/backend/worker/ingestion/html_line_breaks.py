import re

# Docling 2.125.0's HTML reader stands U+E000 in for a <br> and leaves it in
# headings. A space, not a newline: a newline would split the heading or a table row.
_LEFT_BREAK = re.compile("[ \t]*[ \t]*")

HTML_SUFFIXES = frozenset({".html", ".htm", ".epub"})


def without_left_breaks(markdown: str) -> str:
    """Docling's markdown of an HTML page or a book, its leftover breaks as spaces."""
    return _LEFT_BREAK.sub(" ", markdown)
