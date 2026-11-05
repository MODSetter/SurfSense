"""A link read as a page: its main text, or why there is none."""

from urllib.parse import unquote, urlsplit

from trafilatura.utils import decode_file

from modules.documents.web_sources.page_reading.page_fetch import fetched_page
from modules.documents.web_sources.page_reading.page_text import page_text
from modules.documents.web_sources.pullers.puller import HostCheck, Pulled
from modules.documents.web_sources.pullers.read_failure import ReadFailedError, Why

_GONE = frozenset({404, 410})
# Text a server sends as itself, such as a README on raw.githubusercontent.com.
_PLAIN = ("text/plain", "text/markdown", "text/x-markdown")


def read_page(url: str, reach: HostCheck) -> Pulled:
    page = fetched_page(url, reach)
    if page.status in _GONE:
        raise ReadFailedError(Why.GONE)
    if page.status >= 400:
        raise ReadFailedError(Why.UNREADABLE)
    if page.body is None:
        raise ReadFailedError(Why.NOT_A_PAGE)
    text = _decoded(page.body, page.content_type)
    if page.content_type.split(";", 1)[0].strip().lower() in _PLAIN:
        if not text.strip():
            raise ReadFailedError(Why.UNREADABLE)
        return Pulled(_file_name(page.url), text.strip())
    pulled = page_text(text, page.url) if text.strip() else None
    if pulled is None:
        raise ReadFailedError(Why.UNREADABLE)
    return pulled


def _decoded(body: bytes, content_type: str) -> str:
    """By the charset the server named; else detected, as trafilatura detects it."""
    for part in content_type.split(";")[1:]:
        key, _, value = part.partition("=")
        charset = value.strip().strip("\"'")
        if key.strip().lower() == "charset" and charset:
            try:
                return body.decode(charset, errors="replace")
            except LookupError:
                break
    return decode_file(body)


def _file_name(url: str) -> str:
    path = urlsplit(url).path.rstrip("/")
    return unquote(path.rsplit("/", 1)[-1]) or url
