import re

# Each stops at the next tag of its kind: left unclosed, as old Mobipocket files
# do, every one would scan to the end of the book, which took minutes on 2 MB.
_PARAGRAPH = re.compile(r"<p\b[^>]*>((?:(?!<p\b).)*?)</p>", re.S | re.I)
_FONT = re.compile(
    r"<font\b[^>]*\bsize=[\"']?([+-]?\d)[\"']?[^>]*>((?:(?!<font\b).)*?)</font>",
    re.S | re.I,
)
_TAG = re.compile(r"<[^>]+>")
# HTML's font sizes run 1 to 7 around a default of 3; 5 and up reads as a title.
_DEFAULT_SIZE = 3
_LEVEL_BY_SIZE = {7: 1, 6: 2, 5: 3}


def with_headings(html: str) -> str:
    """MOBI 6 keeps no <h1>-<h6>: a paragraph set wholly in a large font becomes
    a heading of its size, so Docling and the chunker see the book's sections."""

    def heading(paragraph: re.Match[str]) -> str:
        level = _level(paragraph.group(1))
        if level is None:
            return paragraph.group(0)
        return f"<h{level}>{paragraph.group(1)}</h{level}>"

    return _PARAGRAPH.sub(heading, html)


def _level(inner: str) -> int | None:
    sizes = [_size(match.group(1)) for match in _FONT.finditer(inner)]
    # Text outside the large type is a paragraph with a big first letter.
    if not sizes or _TAG.sub("", _FONT.sub("", inner)).strip():
        return None
    return _LEVEL_BY_SIZE.get(min(sizes))


def _size(value: str) -> int:
    size = _DEFAULT_SIZE + int(value) if value[0] in "+-" else int(value)
    return max(1, min(size, 7))
