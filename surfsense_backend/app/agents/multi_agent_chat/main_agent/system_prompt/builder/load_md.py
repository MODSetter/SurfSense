"""Load main-agent-only markdown from ``system_prompt/markdown/`` (``importlib.resources``)."""

from __future__ import annotations

from importlib import resources

_PROMPTS_PACKAGE = "app.agents.multi_agent_chat.main_agent.system_prompt.markdown"


def read_prompt_md(filename: str) -> str:
    """Load ``markdown/{filename}`` (e.g. ``agent_private.md`` or ``tools/_preamble.md``)."""
    ref = resources.files(_PROMPTS_PACKAGE).joinpath(filename)
    if not ref.is_file():
        return ""
    text = ref.read_text(encoding="utf-8")
    return text[:-1] if text.endswith("\n") else text
