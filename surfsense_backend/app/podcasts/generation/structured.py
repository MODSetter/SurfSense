"""Parse a model's reply into a Pydantic shape, tolerating chatty output.

Agent LLMs return JSON wrapped in prose, markdown fences, or reasoning blocks.
This mirrors the legacy podcaster's resilient parsing — strip fences, then fall
back to the outermost ``{...}`` span — so every generation node validates the
reply the same way instead of repeating ad-hoc parsing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel, ValidationError

from app.utils.content_utils import extract_text_content, strip_markdown_fences

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(RuntimeError):
    """The model reply could not be parsed into the expected shape."""


async def invoke_json(llm, messages: list[BaseMessage], model: type[T]) -> T:
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
            raise StructuredOutputError(
                f"could not parse {model.__name__} from model reply"
            ) from exc

    raise StructuredOutputError(
        f"no JSON object found for {model.__name__} in model reply"
    )
