import json

from modules.agent.model_endpoint.error_replies import as_error_body
from modules.agent.model_endpoint.relay import Refusal
from modules.llm.connections.console_refusals import (
    PROVIDER_REFUSED,
    console_words,
    is_final_refusal,
)


def refusal_for(url: str) -> Refusal:
    """The refusal opencode reads from this address, coded where no retry fixes it."""

    def refusal(status_code: int, content: bytes) -> tuple[int, bytes]:
        body = as_error_body(content, status_code)
        if not is_final_refusal(url, status_code, content):
            return status_code, body
        # The code reaches the turn's error frame, as a plan's refusal does.
        words = console_words(json.loads(body)["error"]["message"])
        coded = {"error": {"message": words, "code": PROVIDER_REFUSED}}
        return status_code, json.dumps(coded).encode()

    return refusal
