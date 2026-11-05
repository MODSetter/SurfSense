import json

from modules.agent.model_endpoint.error_replies import as_error_body
from modules.agent.model_endpoint.relay import Refusal
from modules.llm.connections.console_refusals import (
    PROVIDER_REFUSED,
    console_words,
    is_final_refusal,
)
from modules.llm.connections.opencode_free_models import (
    FREE_MODEL_REASON,
    explained_refusal,
    is_free_model_refusal,
)


def refusal_for(url: str) -> Refusal:
    """The refusal opencode reads from this address, with OpenCode's rule named."""

    def refusal(status_code: int, content: bytes) -> tuple[int, bytes]:
        body = as_error_body(content, status_code)
        if is_final_refusal(url, status_code, content):
            # The code reaches the turn's error frame, as a plan's refusal does.
            words = console_words(json.loads(body)["error"]["message"])
            coded = {"error": {"message": words, "code": PROVIDER_REFUSED}}
            return status_code, json.dumps(coded).encode()
        if not is_free_model_refusal(url, status_code):
            return status_code, body
        if not content.strip():
            message = FREE_MODEL_REASON
        else:
            message = explained_refusal(
                url, status_code, json.loads(body)["error"]["message"]
            )
        return status_code, json.dumps({"error": {"message": message}}).encode()

    return refusal
