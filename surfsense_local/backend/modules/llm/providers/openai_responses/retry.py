import httpx

# A plan's endpoint throttles briefly under load; these are worth waiting out.
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

# Twice, then the failure is the reply's: a person retries what is still failing.
MAX_RETRIES = 2

# The longest one wait may be, whatever the endpoint asks for.
MAX_WAIT_SECONDS = 60.0


def retry_wait(reply: httpx.Response, attempt: int) -> float:
    """How long to wait before retry number `attempt` (0 first): what the
    endpoint asks for, at most a minute, else one then two seconds."""
    asked = _seconds(reply.headers.get("retry-after-ms"), per=1000.0)
    if asked is None:
        asked = _seconds(reply.headers.get("retry-after"), per=1.0)
    if asked is None:
        asked = float(2**attempt)
    return min(MAX_WAIT_SECONDS, max(0.0, asked))


def _seconds(value: str | None, *, per: float) -> float | None:
    if value is None:
        return None
    try:
        return float(value) / per
    except ValueError:
        return None
