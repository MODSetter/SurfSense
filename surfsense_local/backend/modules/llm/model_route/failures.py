import httpx

from modules.egress.service import EgressDeniedError
from modules.llm.activity import ModelBusyError
from modules.llm.providers.openai_responses.errors import (
    PlanLimitError,
    SignInRequiredError,
)
from modules.llm.providers.stream_deadline import StreamTimeoutError
from modules.llm.resolution import ModelResolutionError


def as_frame(failure: Exception) -> dict:
    """A generation's failure, as the worker needs it to raise the same type."""
    message = str(failure)
    if isinstance(failure, httpx.HTTPStatusError):
        return {
            "type": "error",
            "error": "http_status",
            "status": failure.response.status_code,
            "message": message,
        }
    if isinstance(failure, StreamTimeoutError):
        return {
            "type": "error",
            "error": "stream_timeout",
            "seconds": failure.seconds,
            "first_item": failure.first_item,
            "message": message,
        }
    if isinstance(failure, SignInRequiredError):
        return {"type": "error", "error": "sign_in_required", "message": message}
    if isinstance(failure, PlanLimitError):
        return {"type": "error", "error": "plan_limit", "message": message}
    if isinstance(failure, EgressDeniedError):
        return {
            "type": "error",
            "error": "egress_denied",
            "destination": failure.destination,
            "message": message,
        }
    # A model being deleted cannot be used either; the worker handles both alike.
    if isinstance(failure, ModelResolutionError | ModelBusyError):
        return {"type": "error", "error": "model_resolution", "message": message}
    if isinstance(failure, httpx.HTTPError):
        return {"type": "error", "error": "transport", "message": message}
    return {"type": "error", "error": "other", "message": message}


def raise_from_frame(frame: dict) -> None:
    """Raise what `as_frame` described, so a caller handles it as it always has."""
    message = frame.get("message", "")
    kind = frame.get("error")
    if kind == "http_status":
        status = int(frame["status"])
        request = httpx.Request("POST", "http://model")
        raise httpx.HTTPStatusError(
            message, request=request, response=httpx.Response(status, request=request)
        )
    if kind == "stream_timeout":
        raise StreamTimeoutError(
            float(frame["seconds"]),
            first_item=bool(frame["first_item"]),
            subject="the model",
        )
    if kind == "sign_in_required":
        raise SignInRequiredError(message)
    if kind == "plan_limit":
        raise PlanLimitError(message)
    if kind == "egress_denied":
        raise EgressDeniedError(frame["destination"])
    if kind == "model_resolution":
        raise ModelResolutionError(message)
    if kind == "transport":
        raise httpx.ConnectError(message)
    raise RuntimeError(message)
