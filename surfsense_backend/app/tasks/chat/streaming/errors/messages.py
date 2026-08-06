"""Canonical user-facing messages for backend-owned chat error codes."""

from __future__ import annotations

from typing import Any

CHAT_ERROR_MESSAGES: dict[str, str] = {
    "MESSAGE_PERSIST_FAILED": (
        "We couldn't save this message. Please try again in a moment."
    ),
    "MODEL_AUTH_FAILED": (
        "This model's API key is invalid or expired. Switch models, or update "
        "the API key."
    ),
    "MODEL_CONTEXT_LIMIT": (
        "This request is too large for the selected model. Ask for less at once, "
        "or lower this model's max input tokens in settings so we send less."
    ),
    "MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT": (
        "The selected model does not support image input. Switch to a "
        "vision-capable model or remove the image attachment and try again."
    ),
    "MODEL_NOT_FOUND": (
        "The selected model is unavailable or no longer exists. Switch to "
        "another model and try again."
    ),
    "MODEL_OUT_OF_MEMORY": (
        "The computer running this model doesn't have enough memory to load it. "
        "Close anything else using the GPU, or switch to a smaller model."
    ),
    "MODEL_PROVIDER_UNAVAILABLE": (
        "The selected model provider is temporarily unavailable. Please try "
        "again or switch models."
    ),
    "NO_ACTIVE_TURN": "There is no active response to stop.",
    "PREMIUM_QUOTA_EXHAUSTED": (
        "Buy more credits to continue with this model, or switch to a free model."
    ),
    "RATE_LIMITED": (
        "This model is temporarily rate-limited. Please try again in a few "
        "seconds or switch models."
    ),
    "SERVER_ERROR": ("We couldn't complete this response right now. Please try again."),
    "THREAD_BUSY": (
        "Another response is still finishing for this thread. Please try again "
        "in a moment."
    ),
    "TOOL_EXECUTION_ERROR": (
        "A tool failed while processing your request. Please try again."
    ),
    "TURN_CANCELLING": (
        "A previous response is still stopping. Please try again in a moment."
    ),
}

_LM_STUDIO_CONTEXT_MESSAGE = (
    "This request is too large for the selected model. Raise the context length "
    "in LM Studio, or lower this model's max input tokens in settings."
)


def chat_error_message(
    error_code: str,
    *,
    details: dict[str, Any] | None = None,
) -> str:
    """Return safe display copy for a backend-owned chat error code."""
    if (
        error_code == "MODEL_CONTEXT_LIMIT"
        and details
        and details.get("provider_error_type") == "exceed_context_size_error"
    ):
        return _LM_STUDIO_CONTEXT_MESSAGE
    try:
        return CHAT_ERROR_MESSAGES[error_code]
    except KeyError as exc:
        raise ValueError(f"No user-facing message registered for {error_code}") from exc
