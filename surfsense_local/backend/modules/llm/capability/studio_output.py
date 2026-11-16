"""Which Studio path a chat model takes: writing its own pages and Office files, or the simple one."""

from typing import Literal

from modules.llm.capability.level import AGENT_LEVELS, Level
from modules.llm.capability.resolve import capability_of
from modules.llm.models import SelectedModel

StudioOutput = Literal["full", "simple"]


def studio_output(selection: SelectedModel) -> StudioOutput:
    """A model measured at the agent's bar writes its own; one measured below, the simple path.

    A model not measured keeps today's rule: remote writes its own, one served
    from this computer (llama.cpp, or Ollama or LM Studio on loopback) the simple path.
    """
    level = capability_of(selection.name, selection.connection).level
    if level in AGENT_LEVELS:
        return "full"
    if level is Level.STUDIO_ONLY:
        return "simple"
    return "simple" if selection.fingerprint.local else "full"
