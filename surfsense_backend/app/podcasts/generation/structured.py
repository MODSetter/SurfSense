"""Parse a model's reply into a Pydantic shape, tolerating chatty output.

Agent LLMs return JSON wrapped in prose, markdown fences, or reasoning blocks,
so a plain ``model_validate_json`` is unreliable. Centralising the tolerant
parse here keeps every generation node validating replies the same way.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel, ValidationError

from app.utils.content_utils import extract_text_content, strip_markdown_fences

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# How much of the raw reply to include in logs when a parse fails, so the actual
# malformation is diagnosable without dumping an entire episode's worth of text.
_LOG_SNIPPET_CHARS = 2000


class StructuredOutputError(RuntimeError):
    """The model reply could not be parsed into the expected shape."""


async def invoke_json[T: BaseModel](
    llm, messages: list[BaseMessage], model: type[T]
) -> T:
    """Invoke ``llm`` and validate its reply as ``model``."""
    response = await llm.ainvoke(messages)
    content = strip_markdown_fences(extract_text_content(response.content))

    try:
        return model.model_validate_json(content)
    except (ValidationError, ValueError):
        pass

    start = content.find("{")
    end = content.rfind("}") + 1
    if 0 <= start < end:
        try:
            return model.model_validate_json(content[start:end])
        except (ValidationError, ValueError) as exc:
            logger.error(
                "Failed to parse %s from model reply: %s\nRaw reply: %s",
                model.__name__,
                exc,
                content[:_LOG_SNIPPET_CHARS],
            )
            raise StructuredOutputError(
                f"could not parse {model.__name__} from model reply: {exc}"
            ) from exc

    logger.error(
        "No JSON object found for %s in model reply.\nRaw reply: %s",
        model.__name__,
        content[:_LOG_SNIPPET_CHARS],
    )
    raise StructuredOutputError(
        f"no JSON object found for {model.__name__} in model reply"
    )
