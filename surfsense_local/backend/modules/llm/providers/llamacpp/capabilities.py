"""What a model can accept, and what its chat template can express.

Two sources, two kinds of fact, and only one of them reaches a person:

    GET /models -> architecture.input_modalities     what the model can ACCEPT
    GET /props  -> chat_template_caps                what the TEMPLATE supports

Template derived rather than guessed from a name. A regex over model names is
how you end up telling someone a model reads images when nothing can hand it
one.
"""

from dataclasses import dataclass
from enum import StrEnum


class Modality(StrEnum):
    TEXT = "text"
    IMAGE = "image"


@dataclass(frozen=True)
class Capabilities:
    """One struct, but not one list that reaches the renderer.

    `system_role` and `typed_content` change how a request is built and mean
    nothing to a person; `vision` is the only thing here anyone chooses a model
    for.
    """

    inputs: tuple[Modality, ...]
    system_role: bool
    typed_content: bool
    tools: bool
    context_tokens: int | None

    @property
    def can_see(self) -> bool:
        """Both halves, because either alone is a lie.

        A model can accept images architecturally while its template takes only
        string content, which leaves no way to send it one.
        """
        return Modality.IMAGE in self.inputs and self.typed_content

    @property
    def user_facing(self) -> tuple[str, ...]:
        """The only capability that is a badge. Everything else is a constraint."""
        return ("vision",) if self.can_see else ()


def read_capabilities(model_id: str, models: dict, props: dict) -> Capabilities:
    """Combine the two reports into one answer about one model.

    Absent fields are read generously, except where being wrong is silent: a
    runtime that does not report `supports_system_role` is assumed to support
    one, because dropping the system message takes the grounding and the
    citation instructions with it and nothing says so.
    """
    row = next(
        (entry for entry in models.get("data", []) if entry.get("id") == model_id),
        {},
    )
    declared = (row.get("architecture") or {}).get("input_modalities") or ["text"]
    inputs = tuple(
        Modality(name) for name in declared if name in set(Modality)
    ) or (Modality.TEXT,)

    template = props.get("chat_template_caps") or {}
    settings = props.get("default_generation_settings") or {}
    return Capabilities(
        inputs=inputs,
        system_role=bool(template.get("supports_system_role", True)),
        typed_content=bool(template.get("supports_typed_content", False)),
        tools=bool(template.get("supports_tools", False)),
        context_tokens=settings.get("n_ctx"),
    )
