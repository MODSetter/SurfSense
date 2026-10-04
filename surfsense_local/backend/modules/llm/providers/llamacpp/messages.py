"""Shaping a conversation for the template that will render it.

The adapter downgrades at this seam so `modules/chat` never learns that
templates differ. It assembles one conversation; what a particular model can be
told is a property of the model, and belongs here.
"""

from collections.abc import Sequence
from dataclasses import replace

from modules.llm.providers.llamacpp.capabilities import Capabilities
from modules.llm.providers.types import Message


def for_template(
    messages: Sequence[Message], capabilities: Capabilities
) -> list[Message]:
    """The same conversation, expressed in what this template can carry.

    A template with no system role gets the instructions folded into the first
    user turn rather than losing them. Dropping them is the silent failure: the
    model answers without the sources or the citation format and sounds exactly
    as confident as it would have otherwise.
    """
    if not capabilities.can_see:
        # A thread keeps its pictures after a switch to a text model and goes on
        # as text; llama-server would refuse the whole turn otherwise.
        messages = [replace(m, images=()) if m.images else m for m in messages]
    if capabilities.system_role:
        return list(messages)

    system = [m for m in messages if m.role == "system"]
    rest = [m for m in messages if m.role != "system"]
    if not system or not rest:
        return list(messages)

    preamble = "\n\n".join(m.content for m in system)
    first, *later = rest
    folded = replace(first, content=f"{preamble}\n\n{first.content}")
    return [folded, *later]
