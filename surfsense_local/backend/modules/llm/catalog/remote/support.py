"""What a remote model can be asked to do in a request.

None is not no: models.dev omits `structured_output` on 2,442 models while
writing `false` on 739 others, and the manifest keeps that difference.
"""

from dataclasses import dataclass

from modules.llm.catalog.remote.manifest.schema import RemoteModel

__all__ = ["Supports", "supports"]


@dataclass(frozen=True)
class Supports:
    """Request features a model accepts. None means models.dev never said."""

    tool_call: bool | None
    reasoning: bool | None
    structured_output: bool | None
    context_window: int | None


def supports(model: RemoteModel) -> Supports:
    """Read the request features off a manifest entry."""
    return Supports(
        tool_call=model.tool_call,
        reasoning=model.reasoning,
        structured_output=model.structured_output,
        context_window=model.context,
    )
