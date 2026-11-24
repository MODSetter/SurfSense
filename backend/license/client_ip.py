"""The caller's address as the proxy in front reports it, in the one header it writes; any header a caller could set is ignored."""

import logging

from starlette.requests import Request

from license.settings import config

logger = logging.getLogger(__name__)

# Headers already reported missing: once per process is enough to tell the operator.
_missing: set[str] = set()


def get_real_client_ip(request: Request) -> str:
    """The header LICENSE_CLIENT_IP_HEADER names (a list's first entry), else the socket peer."""
    header = config.LICENSE_CLIENT_IP_HEADER
    if header:
        named = request.headers.get(header, "").split(",")[0].strip()
        if named:
            return named
        if header not in _missing:
            _missing.add(header)
            # The header, never the address: no log line keeps a caller's.
            logger.warning(
                "A request came without the %s header LICENSE_CLIENT_IP_HEADER names, "
                "so the rate limits count it under the socket's peer: if that is the "
                "proxy, every caller shares one bucket.",
                header,
            )
    return request.client.host if request.client else "127.0.0.1"
