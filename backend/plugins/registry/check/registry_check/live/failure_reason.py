"""A failure in words that carry nothing a server sent: a pull request's log is public.

The SDK quotes a bad answer in its errors, so an error's own message is never printed.
"""

import httpx2


def failure_reason(error: BaseException) -> str:
    if isinstance(error, httpx2.TimeoutException):
        return "timed out"
    if isinstance(error, httpx2.ConnectError):
        return "the connection failed"
    return type(error).__name__
