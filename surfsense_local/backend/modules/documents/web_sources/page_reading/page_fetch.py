"""One page fetched as Chrome asks for it, following the site's redirects one hop at a time.

Each hop to a new host is checked before it connects, so a redirect never reaches
a host the user has not allowed. No browser: stealth browsers would not fit the
installer, so a page only scripts can build is not read.
"""

from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urljoin, urlsplit

from curl_cffi.curl import CurlError
from curl_cffi.requests import Response, Session

from modules.documents.web_sources.pullers.puller import HostCheck
from modules.documents.web_sources.pullers.read_failure import ReadFailedError, Why
from modules.egress.service import EgressDeniedError

# A browser's own limit is 20; past ten, a site is looping.
MAX_HOPS = 10
# Connect (TLS included), then the whole response.
TIMEOUT = (10.0, 60.0)
# Far past any article; the rest of a bigger page is not read.
MAX_BYTES = 20 * 1024 * 1024
_REDIRECTS = frozenset({301, 302, 303, 307, 308})
# Web Crawl sent it too: some sites let a reader arriving from Google through.
_REFERER = "https://www.google.com/"


@dataclass(frozen=True)
class FetchedPage:
    # Where the redirects ended.
    url: str
    status: int
    content_type: str
    # None for an answer that is not text, such as a PDF: never downloaded.
    body: bytes | None


def fetched_page(url: str, reach: HostCheck) -> FetchedPage:
    """Raises EgressDeniedError when the link's own host is not allowed, else ReadFailedError."""
    reach(urlsplit(url).hostname or "")
    with Session() as session:
        for _ in range(MAX_HOPS + 1):
            response = _asked(session, url)
            try:
                location = response.headers.get("location")
                if response.status_code in _REDIRECTS and location:
                    url = _next_hop(url, location, reach)
                    continue
                content_type = response.headers.get("content-type") or ""
                body = _body(response) if _readable(content_type) else None
            finally:
                response.close()
            return FetchedPage(url, response.status_code, content_type, body)
    raise ReadFailedError(Why.UNREADABLE)


def _asked(session: Session, url: str) -> Response:
    try:
        return session.get(
            url,
            impersonate="chrome",
            referer=_REFERER,
            timeout=TIMEOUT,
            allow_redirects=False,
            stream=True,
        )
    except CurlError as error:
        raise ReadFailedError(Why.UNREACHABLE) from error


def _readable(content_type: str) -> bool:
    """Only text is downloaded: a PDF behind a link is refused before its bytes arrive."""
    kind = content_type.split(";", 1)[0].strip().lower()
    return not kind or kind.startswith("text/") or kind.endswith(("+xml", "/xml"))


def _body(response: Response) -> bytes:
    chunks: list[bytes] = []
    size = 0
    try:
        for chunk in response.iter_content():
            chunks.append(chunk)
            size += len(chunk)
            if size >= MAX_BYTES:
                break
    except CurlError as error:
        raise ReadFailedError(Why.UNREACHABLE) from error
    return b"".join(chunks)[:MAX_BYTES]


def _next_hop(url: str, location: str, reach: HostCheck) -> str:
    """The redirect's target, once its host is allowed; a host not allowed is MOVED."""
    try:
        target = urljoin(url, location.strip())
        parts = urlsplit(target)
    except ValueError as malformed:
        raise ReadFailedError(Why.UNREADABLE) from malformed
    host = parts.hostname or ""
    if parts.scheme not in ("http", "https") or not host:
        raise ReadFailedError(Why.UNREADABLE)
    here = urlsplit(url).hostname or ""
    if host == here:
        return target
    # A public page may not send the read into this machine or its network,
    # where the app's own API and the user's devices answer.
    if _own_network(host) and not _own_network(here):
        raise ReadFailedError(Why.UNREADABLE)
    try:
        reach(host)
    except EgressDeniedError as refused:
        raise ReadFailedError(Why.MOVED, host) from refused
    return target


def _own_network(host: str) -> bool:
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return not ip_address(host).is_global
    except ValueError:
        return False
