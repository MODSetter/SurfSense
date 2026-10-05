"""Which models count as strong enough to write a document script."""

from modules.llm.capability import AGENT_LEVELS, Level, capability_of
from modules.llm.models import SelectedModel


def writes_script(selection: SelectedModel) -> bool:
    """A model measured at the agent's bar writes a script, one measured to fail Markdown.

    A model not measured keeps today's rule: remote writes a script, one served
    from this computer (llama.cpp, or Ollama or LM Studio on loopback) Markdown.
    """
    level = capability_of(selection.name, selection.connection).level
    if level in AGENT_LEVELS:
        return True
    if level is Level.STUDIO_ONLY:
        return False
    return not selection.fingerprint.local
