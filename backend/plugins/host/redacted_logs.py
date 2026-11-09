"""Credentials never reach the host's logs, and web addresses keep only their host.

Scrapling logs a failed proxy as the URL it was given, user and password included,
and a library's error can quote a URL or a request it sent. Each log record is
redacted as it is made, its message, arguments, traceback and stack alike, so no
logger or handler, the host's or a library's, can write a credential out. An
http(s) or ws(s) URL keeps only its scheme and host, up to the first space: its
path and query name what a user asked for, and plugin records are kept only for
rate limits, abuse and billing. An address without its scheme, or with escaped
slashes, is not recognised.
"""

import logging
import re
from collections.abc import Mapping
from typing import Any

REDACTED = "***"

_REDACTIONS = (
    # A URL's user and password before its host, the form every proxy is given in.
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
    # Last, so a credential in a query is hidden first: a web address's path and
    # query, its scheme in any case, leaving out at most one punctuation mark
    # that ends a sentence after it. An apostrophe followed by a letter, a digit
    # or one of & = + % - / # is inside the address (patient's, patients'+rights);
    # any other one closes a quote around it.
    (
        re.compile(
            r"""(\b(?:https?|wss?)://[^\s/?#'"<>]+)[/?#]"""
            r"""(?:[^\s'"<>]|'(?=[\w&=+%/#-]))*"""
            r"""(?:[^\s'"<>.,;:!?)\]]|[.,;:!?)\]](?=[.,;:!?)\]]))""",
            re.IGNORECASE,
        ),
        rf"\1/{REDACTED}",
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
    # The arguments keep their shape, since a formatter may read them: uvicorn's
    # access log unpacks its five. Only one that holds a credential is replaced,
    # and a template with arguments is left whole, so its placeholders still match.
    if isinstance(record.args, Mapping):
        record.args = {key: _redacted_value(v) for key, v in record.args.items()}
    elif isinstance(record.args, tuple) and record.args:
        record.args = tuple(_redacted_value(arg) for arg in record.args)
    else:
        record.msg = _redacted_value(record.msg)
    try:
        message = record.getMessage()
    except Exception:
        # A message that does not format is the logging module's own error to report.
        return
    # A credential split across the message and its arguments shows only once
    # formatted; such a record keeps just its redacted text.
    if redacted(message) != message:
        record.msg, record.args = redacted(message), None
    if record.exc_info and not record.exc_text:
        record.exc_text = redacted(logging.Formatter().formatException(record.exc_info))
    if record.stack_info:
        record.stack_info = redacted(record.stack_info)


def _redacted_value(value: Any) -> Any:
    """A string redacted; anything else as it is, unless its text holds a credential."""
    if isinstance(value, str):
        return redacted(value)
    try:
        text = str(value)
    except Exception:
        return value
    clean = redacted(text)
    return value if clean == text else clean
