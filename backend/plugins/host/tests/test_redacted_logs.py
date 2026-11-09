import logging
from collections.abc import Iterator

import pytest
from uvicorn.logging import AccessFormatter

from host.redacted_logs import redact_every_record, redacted

PROXY = "http://user-1__cr.us:s3cr%40t@gw.dataimpulse.com:823"
HIDDEN = "http://***@gw.dataimpulse.com:823"


@pytest.mark.parametrize(
    ("text", "shown"),
    [
        # Scrapling's own warning when a proxy fails.
        (
            f"Proxy '{PROXY}' failed (attempt 1) | Retrying in 1s...",
            f"Proxy '{HIDDEN}' failed (attempt 1) | Retrying in 1s...",
        ),
        (
            "{'server': 'http://gw.dataimpulse.com:823', 'username': 'user-1', "
            "'password': 's3cret'}",
            "{'server': 'http://gw.dataimpulse.com:823', 'username': 'user-1', "
            "'password': '***'}",
        ),
        (
            "proxy user-1:s3cret@gw.dataimpulse.com:823 refused",
            "proxy ***@gw.dataimpulse.com:823 refused",
        ),
        ('{"clientKey": "CAP-123", "task": {}}', '{"clientKey": "***", "task": {}}'),
        (
            "GET https://2captcha.com/res.php?key=abc123&action=get",
            "GET https://2captcha.com/***",
        ),
    ],
)
def test_credentials_are_hidden(text: str, shown: str) -> None:
    assert redacted(text) == shown


@pytest.mark.parametrize(
    ("text", "shown"),
    [
        (
            "Amazon request failed for https://www.amazon.com/dp/B0CX23V2ZK?th=1: 403",
            "Amazon request failed for https://www.amazon.com/***: 403",
        ),
        (
            'navigating to "https://www.tiktok.com/@natgeo/video/7", waiting until "load"',
            'navigating to "https://www.tiktok.com/***", waiting until "load"',
        ),
        (
            "GET https://www.google.com/search?q=private+clinic+near+me failed",
            "GET https://www.google.com/*** failed",
        ),
        (
            "https://plugins.surfsense.com/web-crawl/mcp answered 502",
            "https://plugins.surfsense.com/*** answered 502",
        ),
        (
            "warmed https://www.indeed.com/ first",
            "warmed https://www.indeed.com/ first",
        ),
        (
            "GET https://example.com/search?q=patient's-record failed",
            "GET https://example.com/*** failed",
        ),
        (
            "tried 'https://one.test/a' and 'https://two.test/b'",
            "tried 'https://one.test/***' and 'https://two.test/***'",
        ),
        (
            "queued ['https://one.test/a','https://two.test/b']",
            "queued ['https://one.test/***','https://two.test/***']",
        ),
        (
            'navigating to "https://example.com/a\'s-record"',
            'navigating to "https://example.com/***"',
        ),
        (
            "GET https://example.com/search?q=patients'&location=clinic failed",
            "GET https://example.com/*** failed",
        ),
        (
            "GET https://example.com/search?patients'=clinic failed",
            "GET https://example.com/*** failed",
        ),
        (
            "GET https://www.google.com/search?q=patients'+rights+lawyer failed",
            "GET https://www.google.com/*** failed",
        ),
        (
            "GET https://www.google.com/search?q=patients'%20rights failed",
            "GET https://www.google.com/*** failed",
        ),
        (
            "GET https://example.com/doctors'-notes/x failed",
            "GET https://example.com/*** failed",
        ),
        (
            "GET https://example.com/patients'/records failed",
            "GET https://example.com/*** failed",
        ),
        (
            "GET https://example.com/search?q=patients'#frag failed",
            "GET https://example.com/*** failed",
        ),
        (
            "GET HTTPS://WWW.GOOGLE.COM/search?q=private+clinic failed",
            "GET HTTPS://WWW.GOOGLE.COM/*** failed",
        ),
        (
            "WSS://example.com/socket?token=abc closed",
            "WSS://example.com/*** closed",
        ),
        (
            "GET https://example.com/?auth=!!!",
            "GET https://example.com/***!",
        ),
    ],
)
def test_a_url_keeps_only_its_host(text: str, shown: str) -> None:
    """The path and query name what a user asked a plugin for; the host is enough to debug."""
    assert redacted(text) == shown


@pytest.mark.parametrize(
    "text",
    [
        "someone@example.com wrote at 10:30",
        "Instagram username natgeo has 3 posts",
    ],
)
def test_text_without_credentials_is_left_alone(text: str) -> None:
    assert redacted(text) == text


@pytest.fixture
def record_factory() -> Iterator[None]:
    """Each test leaves logging's record factory as it found it."""
    make = logging.getLogRecordFactory()
    yield
    logging.setLogRecordFactory(make)


def test_every_record_is_redacted_whoever_formats_it(
    record_factory: None, caplog: pytest.LogCaptureFixture
) -> None:
    """The message, its arguments and the traceback, before any handler sees them."""
    redact_every_record()
    logger = logging.getLogger("host.tests.redacted")
    with caplog.at_level(logging.WARNING, logger=logger.name):
        logger.warning(f"Proxy '{PROXY}' failed (attempt 1)")
        logger.warning("proxy session open failed: %s", PROXY)
        try:
            raise ConnectionError(f"tunnel to {PROXY} refused")
        except ConnectionError:
            logger.exception("fetch failed")

    assert [record.getMessage() for record in caplog.records] == [
        f"Proxy '{HIDDEN}' failed (attempt 1)",
        f"proxy session open failed: {HIDDEN}",
        "fetch failed",
    ]
    assert "s3cr" not in caplog.text
    assert f"tunnel to {HIDDEN} refused" in caplog.text


def test_a_url_inside_an_error_is_cut_to_its_host(
    record_factory: None, caplog: pytest.LogCaptureFixture
) -> None:
    redact_every_record()
    logger = logging.getLogger("host.tests.redacted.url")
    with caplog.at_level(logging.WARNING, logger=logger.name):
        logger.warning(
            "fetch failed: %s",
            TimeoutError('page.goto: navigating to "https://www.amazon.com/dp/B0X1"'),
        )

    (record,) = caplog.records
    assert record.getMessage() == (
        'fetch failed: page.goto: navigating to "https://www.amazon.com/***"'
    )
    assert "B0X1" not in caplog.text


def test_a_formatter_that_reads_the_arguments_still_formats(
    record_factory: None, caplog: pytest.LogCaptureFixture
) -> None:
    """uvicorn's access log unpacks its five arguments: they keep their shape and types."""
    redact_every_record()
    logger = logging.getLogger("host.tests.redacted.access")
    with caplog.at_level(logging.INFO, logger=logger.name):
        logger.info(
            '%s - "%s %s HTTP/%s" %d',
            "10.0.1.7:51234",
            "POST",
            "/web-crawl/mcp?key=abc123",
            "1.1",
            200,
        )

    (record,) = caplog.records
    assert record.args == (
        "10.0.1.7:51234",
        "POST",
        "/web-crawl/mcp?key=***",
        "1.1",
        200,
    )
    formatted = AccessFormatter("%(request_line)s %(status_code)s").format(record)
    assert formatted == "POST /web-crawl/mcp?key=*** HTTP/1.1 200 OK"


def test_a_credential_split_across_message_and_arguments_is_hidden(
    record_factory: None, caplog: pytest.LogCaptureFixture
) -> None:
    redact_every_record()
    logger = logging.getLogger("host.tests.redacted.split")
    with caplog.at_level(logging.WARNING, logger=logger.name):
        logger.warning("proxy http://%s:%s@%s failed", "user-1", "s3cret", "gw:823")
        logger.warning("open failed: %s", ConnectionError(f"tunnel to {PROXY} refused"))

    assert [record.getMessage() for record in caplog.records] == [
        "proxy http://***@gw:823 failed",
        f"open failed: tunnel to {HIDDEN} refused",
    ]


def test_redacting_twice_wraps_the_factory_once(record_factory: None) -> None:
    redact_every_record()
    once = logging.getLogRecordFactory()
    redact_every_record()

    assert logging.getLogRecordFactory() is once
