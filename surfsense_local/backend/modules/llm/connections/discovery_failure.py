import httpx
from fastapi import HTTPException, status

_AUTH_STATUS_CODES = {401, 403}


def discovery_failure(error: httpx.HTTPError) -> HTTPException:
    """A 502 whose code says what the endpoint did, so the UI can name the fix.

    By exception type and status only, never the message text, as chat's
    classify_chat_error does.
    """
    if isinstance(error, httpx.HTTPStatusError):
        answered = error.response.status_code
        if answered in _AUTH_STATUS_CODES:
            code = "provider_auth"
        elif answered == 429:
            code = "provider_rate_limited"
        else:
            code = "provider_error"
    elif isinstance(error, httpx.TransportError):
        code = "provider_unreachable"
    else:
        code = "provider_error"
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        {"code": code, "message": "connection model discovery failed"},
    )
