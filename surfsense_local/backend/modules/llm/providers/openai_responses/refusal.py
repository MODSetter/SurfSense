import json

import httpx

from modules.llm.providers.openai_responses.errors import (
    PlanLimitError,
    SignInRequiredError,
)

MAX_ERROR_CHARS = 400
USAGE_LIMIT = "subscription_sharing_usage_limit_exceeded"
INVALID_USER = "subscription_sharing_invalid_user"


def refused(code: str | None, message: str, response: httpx.Response) -> Exception:
    """The exception a refusal stands for, before or inside the stream alike."""
    if code == USAGE_LIMIT:
        return PlanLimitError(message)
    if code == INVALID_USER:
        return SignInRequiredError(message)
    # httpx's own type, so the chat's status-based classification applies as is.
    return httpx.HTTPStatusError(message, request=response.request, response=response)


async def read_refusal(reply: httpx.Response) -> tuple[str | None, str]:
    """The error code and message of a refused request.

    The plan's direct route can answer `{"detail": "..."}` instead of an API
    error object, so both shapes are read.
    """
    fallback = f"the endpoint returned HTTP {reply.status_code}"
    try:
        payload = json.loads(await reply.aread())
    except (httpx.HTTPError, json.JSONDecodeError, UnicodeDecodeError):
        return None, fallback
    if not isinstance(payload, dict):
        return None, fallback
    return error_fields(payload.get("error"), payload.get("detail"), fallback)


def error_fields(
    error: object, detail: object = None, fallback: str = "the model failed"
) -> tuple[str | None, str]:
    code = error.get("code") if isinstance(error, dict) else None
    message = error.get("message") if isinstance(error, dict) else detail
    text = message.strip() if isinstance(message, str) and message.strip() else fallback
    return (code if isinstance(code, str) else None), text[:MAX_ERROR_CHARS]
