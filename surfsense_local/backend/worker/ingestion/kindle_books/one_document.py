import re

_BODY = re.compile(r"<body\b[^>]*>(.*)</body>", re.S | re.I)


def one_document(files: list[str]) -> str:
    """A KF8 book's files as one HTML page, so Docling reads it once, in order."""
    bodies = [
        match.group(1) if (match := _BODY.search(page)) else page for page in files
    ]
    return "<html><body>" + "\n".join(bodies) + "</body></html>"
