import json
from collections.abc import AsyncIterator

import httpx

from modules.llm.providers.openai_responses.refusal import error_fields, refused
from modules.llm.providers.openai_responses.stream_endings import (
    COMPLETED,
    FAILED,
    INCOMPLETE,
)
from modules.llm.providers.prompt_reuse import log_reuse, response_reuse
from modules.llm.providers.types import Delta

_ANSWER = "response.output_text.delta"
# Summaries are what a plan sends of a trace; the raw trace is kept apart too.
_TRACE = {"response.reasoning_summary_text.delta", "response.reasoning_text.delta"}


async def deltas(reply: httpx.Response) -> AsyncIterator[Delta]:
    """The reply's text as it streams, ending only on `response.completed`.

    A stream that closes without it, or ends `incomplete`, is not an answer:
    the plan's endpoint says to treat nothing as done before that event.
    """
    async for line in reply.aiter_lines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if not payload or payload == "[DONE]":
            continue
        event = json.loads(payload)
        kind = event.get("type")
        if kind == _ANSWER and (text := event.get("delta")):
            yield Delta(text)
        elif kind in _TRACE and (text := event.get("delta")):
            yield Delta(text, reasoning=True)
        elif kind == COMPLETED:
            response = event.get("response")
            if isinstance(response, dict) and (reuse := response_reuse(response)):
                log_reuse(str(response.get("model")), reuse)
            return
        elif kind in FAILED:
            response = event.get("response")
            error = response.get("error") if isinstance(response, dict) else None
            raise refused(*error_fields(error or event), reply)
        elif kind == INCOMPLETE:
            raise httpx.RemoteProtocolError(
                "the model stopped before finishing its reply"
            )
    raise httpx.RemoteProtocolError("the reply ended before the model finished it")
