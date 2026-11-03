"""Redirects, hop by hop, with each new host checked before it is contacted.

curl_cffi's session is answered here, so a test can name any host.
"""

from collections.abc import Iterator

import pytest
from curl_cffi.requests import Session

from modules.documents.web_sources.page_reading import page_fetch
from modules.documents.web_sources.page_reading.page_fetch import fetched_page
from modules.documents.web_sources.pullers.read_failure import ReadFailedError, Why
from modules.egress.service import EgressDeniedError

pytestmark = pytest.mark.unit


class Answer:
    """A response as the reader uses one."""

    def __init__(self, status: int, headers: dict[str, str], body: bytes = b""):
        self.status_code = status
        self.headers = headers
        self.body = body
        self.read = False

    def iter_content(self) -> Iterator[bytes]:
        self.read = True
        yield from (self.body[i : i + 4] for i in range(0, len(self.body), 4))

    def close(self) -> None:
        pass


class Web:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, answers: dict[str, Answer]):
        self.answers = answers
        self.asked: list[str] = []
        self.checked: list[str] = []
        web = self

        def get(_session: Session, url: str, **_: object) -> Answer:
            web.asked.append(url)
            return web.answers[url]

        monkeypatch.setattr(Session, "get", get)

    def reach(self, allowed: set[str]):
        """The pull's host check, allowing `allowed` alone."""

        def check(host: str) -> None:
            self.checked.append(host)
            if host not in allowed:
                raise EgressDeniedError(f"host:{host}", host)

        return check


def moved(to: str, status: int = 302) -> Answer:
    """A redirect answer."""
    return Answer(status, {"location": to})


HTML = {"content-type": "text/html; charset=utf-8"}


def test_a_page_moved_to_a_host_not_allowed_is_not_followed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MOVED names the host, which is never contacted."""
    web = Web(
        monkeypatch, {"https://tides.example/a": moved("https://www.tides.example/a")}
    )

    with pytest.raises(ReadFailedError) as failed:
        fetched_page("https://tides.example/a", web.reach({"tides.example"}))

    assert (failed.value.why, failed.value.host) == (Why.MOVED, "www.tides.example")
    assert web.asked == ["https://tides.example/a"]


def test_a_page_moved_to_an_allowed_host_is_read_there(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A relative location resolves against the page that sent it."""
    web = Web(
        monkeypatch,
        {
            "https://tides.example/a": moved("https://www.tides.example/a", 301),
            "https://www.tides.example/a": moved("/b", 308),
            "https://www.tides.example/b": Answer(200, HTML, b"<p>tides</p>"),
        },
    )

    page = fetched_page(
        "https://tides.example/a", web.reach({"tides.example", "www.tides.example"})
    )

    assert (page.url, page.status, page.body) == (
        "https://www.tides.example/b",
        200,
        b"<p>tides</p>",
    )
    assert web.checked == ["tides.example", "www.tides.example"]


def test_a_public_page_cannot_send_the_read_into_this_machine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Where the app's own API answers, and the user's devices: never asked about."""
    web = Web(
        monkeypatch, {"https://tides.example/a": moved("http://127.0.0.1:8000/docs")}
    )

    with pytest.raises(ReadFailedError) as failed:
        fetched_page("https://tides.example/a", web.reach({"tides.example"}))

    assert failed.value.why is Why.UNREADABLE
    assert web.checked == ["tides.example"]
    assert web.asked == ["https://tides.example/a"]


def test_a_site_redirecting_in_a_loop_is_given_up_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """As a browser gives up."""
    web = Web(
        monkeypatch,
        {
            "https://tides.example/a": moved("/b"),
            "https://tides.example/b": moved("/a"),
        },
    )

    with pytest.raises(ReadFailedError) as failed:
        fetched_page("https://tides.example/a", web.reach({"tides.example"}))

    assert failed.value.why is Why.UNREADABLE
    assert len(web.asked) == page_fetch.MAX_HOPS + 1


def test_the_links_own_host_not_allowed_is_the_pulls_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Turned off since the click: nothing is sent."""
    web = Web(monkeypatch, {})

    with pytest.raises(EgressDeniedError):
        fetched_page("https://tides.example/a", web.reach(set()))

    assert web.asked == []


def test_a_file_behind_a_link_is_never_downloaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A PDF's bytes stay on the server: only its type is read."""
    pdf = Answer(200, {"content-type": "application/pdf"}, b"%PDF-1.7")
    web = Web(monkeypatch, {"https://tides.example/table.pdf": pdf})

    page = fetched_page("https://tides.example/table.pdf", web.reach({"tides.example"}))

    assert page.body is None
    assert pdf.read is False


def test_a_page_past_the_size_limit_is_read_up_to_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rest of a bigger page is not read."""
    monkeypatch.setattr(page_fetch, "MAX_BYTES", 10)
    web = Web(monkeypatch, {"https://tides.example/a": Answer(200, HTML, b"x" * 100)})

    page = fetched_page("https://tides.example/a", web.reach({"tides.example"}))

    assert page.body == b"x" * 10
