"""A registration a provider refuses is an answer SurfSense handles, logged as one line of
its own. The SDK logs it as an error with a traceback, which reads as a crash."""

import logging

from mcp.client.auth.exceptions import OAuthRegistrationError

_SDK = logging.getLogger("mcp.client.auth.oauth2")


class _HandledRefusal(logging.Filter):
    """Every other sign-in error the SDK logs is kept, traceback and all."""

    def filter(self, record: logging.LogRecord) -> bool:
        raised = record.exc_info[1] if record.exc_info else None
        return not isinstance(raised, OAuthRegistrationError)


def quiet_handled_refusals() -> None:
    if not any(isinstance(kept, _HandledRefusal) for kept in _SDK.filters):
        _SDK.addFilter(_HandledRefusal())
