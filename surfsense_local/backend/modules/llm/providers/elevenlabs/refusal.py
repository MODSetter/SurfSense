"""ElevenLabs' words for a refusal. `detail` is an object, a string or a list,
and not every object has `code`, so `message` is what is read."""

import httpx

__all__ = ["refusal_message"]


def refusal_message(reply: httpx.Response) -> str:
    try:
        detail = reply.json()["detail"]
    except (ValueError, KeyError, TypeError):
        return f"HTTP {reply.status_code}"
    if isinstance(detail, str) and detail:
        return detail
    if isinstance(detail, dict) and detail.get("message"):
        return str(detail["message"])
    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        return str(detail[0].get("msg") or f"HTTP {reply.status_code}")
    return f"HTTP {reply.status_code}"
