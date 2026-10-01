"""Errors as opencode's OpenAI-compatible provider reads them: `{"error": {"message": …}}`.

opencode shows that message, and reads a full window from its wording, so a
model's own error passes through with its words intact.
"""

import json

from fastapi.responses import JSONResponse

MAX_MESSAGE_CHARS = 400


def error_reply(
    status_code: int, message: str, code: str | None = None
) -> JSONResponse:
    """An error SurfSense raises itself, before the model is asked."""
    error: dict[str, str] = {"message": message}
    if code:
        error["code"] = code
    return JSONResponse({"error": error}, status_code=status_code)


def as_error_body(content: bytes, status_code: int) -> bytes:
    """A model's error reply, unchanged when it already has a message, wrapped when not."""
    try:
        body = json.loads(content)
    except ValueError:
        body = None
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return content
        if isinstance(error, str):
            return json.dumps({"error": {"message": error}}).encode()
    text = content.decode(errors="replace").strip()[:MAX_MESSAGE_CHARS]
    return json.dumps(
        {"error": {"message": text or f"the model answered {status_code}"}}
    ).encode()
