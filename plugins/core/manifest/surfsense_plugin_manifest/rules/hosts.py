"""A host a plugin declares: exactly what the egress prompt shows and the grant matches."""

import re
from ipaddress import ip_address
from typing import Annotated

from pydantic import AfterValidator

# Lowercase, because the app keys its egress grants on lowercase hostnames.
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def _host(value: str) -> str:
    if _is_loopback(value):
        raise ValueError("loopback is the app itself, not egress, so it is not a host")
    if not (_is_address(value) or _is_hostname(value)):
        raise ValueError(
            "must be a lowercase hostname alone: no scheme, port, path or wildcard"
        )
    return value


def _is_loopback(value: str) -> bool:
    if value == "localhost" or value.endswith(".localhost"):
        return True
    return _is_address(value) and ip_address(value).is_loopback


def _is_address(value: str) -> bool:
    try:
        ip_address(value)
    except ValueError:
        return False
    return True


def _is_hostname(value: str) -> bool:
    labels = value.split(".")
    return len(value) <= 253 and all(_LABEL.fullmatch(label) for label in labels)


Host = Annotated[str, AfterValidator(_host)]
