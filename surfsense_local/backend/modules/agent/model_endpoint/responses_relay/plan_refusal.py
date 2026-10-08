"""A plan's refusal, told to opencode in the chat's own kinds and in a status it does not retry."""

import json

from modules.agent.model_endpoint.error_replies import as_error_body
from modules.llm.providers.openai_responses.refusal import INVALID_USER, USAGE_LIMIT


def plan_refusal(status: int, content: bytes) -> tuple[int, bytes]:
    """A used-up plan as 403, not 429, which opencode would retry until the plan resets."""
    body = json.loads(as_error_body(content, status))
    error = body["error"]
    if error.get("code") == USAGE_LIMIT:
        return 403, _coded(error["message"], "subscription_limit")
    if error.get("code") == INVALID_USER or status == 401:
        return 401, _coded(error["message"], "subscription_sign_in")
    return status, json.dumps(body).encode()


def _coded(message: str, code: str) -> bytes:
    return json.dumps({"error": {"message": message, "code": code}}).encode()
