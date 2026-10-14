import logging
from collections.abc import Iterator

import pytest

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
            "GET https://2captcha.com/res.php?key=***&action=get",
        ),
    ],
)
def test_credentials_are_hidden(text: str, shown: str) -> None:
    assert redacted(text) == shown


@pytest.mark.parametrize(
    "text",
    [
        "https://plugins.surfsense.com/web-crawl/mcp answered 502",
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


def test_redacting_twice_wraps_the_factory_once(record_factory: None) -> None:
    redact_every_record()
    once = logging.getLogRecordFactory()
    redact_every_record()

    assert logging.getLogRecordFactory() is once
