"""Credentials never reach the host's logs.

Scrapling logs a failed proxy as the URL it was given, user and password included,
and a library's error can quote a URL or a request it sent. Each log record is
redacted as it is made, its message, arguments, traceback and stack alike, so no
logger or handler, the host's or a library's, can write a credential out.
"""

import logging
import re
from typing import Any

REDACTED = "***"

_REDACTIONS = (
    # scheme://user:password@host, the form every proxy is given in.
    (
        re.compile(r"(\b[a-zA-Z][a-zA-Z0-9+.-]*://)[^\s/?#@'\"<>]+@"),
        rf"\1{REDACTED}@",
    ),
    # user:password@host:port, the form the captcha solvers send a proxy in.
    (
        re.compile(r"(?<![\w/@:.-])[^\s'\"/@:]+:[^\s'\"/@]+@(?=[\w.-]+:\d+)"),
        f"{REDACTED}@",
    ),
    # A password or a solver's key as a field: key=..., 'password': '...', "clientKey": "...".
    (
        re.compile(
            r"""(\b(?:password|passwd|api_?key|client_?key|key)['"]?\s*[:=]\s*['"]?)"""
            r"""[^'"\s,&}]+""",
            re.IGNORECASE,
        ),
        rf"\1{REDACTED}",
    ),
)


def redacted(text: str) -> str:
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def redact_every_record() -> None:
    """Every log record this process makes from now on is redacted; once is enough."""
    make = logging.getLogRecordFactory()
    if getattr(make, "redacts", False):
        return

    def make_redacted(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = make(*args, **kwargs)
        _redact(record)
        return record

    make_redacted.redacts = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(make_redacted)


def _redact(record: logging.LogRecord) -> None:
    try:
        message = record.getMessage()
    except Exception:
        # A message that does not format is the logging module's own error to report.
        return
    record.msg, record.args = redacted(message), None
    if record.exc_info and not record.exc_text:
        record.exc_text = redacted(logging.Formatter().formatException(record.exc_info))
    if record.stack_info:
        record.stack_info = redacted(record.stack_info)
