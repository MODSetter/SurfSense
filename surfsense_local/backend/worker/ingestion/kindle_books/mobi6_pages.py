import re

_BODY = re.compile(r"<body\b[^>]*>(.*)</body>", re.S | re.I)
_PAGE_BREAK = re.compile(r"<mbp:pagebreak\s*/?>(?:\s*</mbp:pagebreak>)?", re.I)


def as_pages(html: str) -> str:
    """Each page between MOBI 6's page breaks in its own <div>. Docling ignores the
    break, so a book of entries with no <p> reached it as one block of megabytes:
    a 4.5 MB dictionary took 80 s to read, and 6 s split."""
    if not _PAGE_BREAK.search(html):
        return html
    body = _BODY.search(html)
    start, end = body.span(1) if body else (0, len(html))
    pages = "".join(f"<div>{page}</div>" for page in _PAGE_BREAK.split(html[start:end]))
    return html[:start] + pages + html[end:]
