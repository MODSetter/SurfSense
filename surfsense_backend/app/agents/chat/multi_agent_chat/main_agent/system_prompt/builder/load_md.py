"""Load main-agent prompt fragments from ``system_prompt/prompts/``."""

from __future__ import annotations

from importlib import resources

_PROMPTS_PACKAGE = "app.agents.chat.multi_agent_chat.main_agent.system_prompt.prompts"


def read_prompt_md(filename: str) -> str:
    """Load ``prompts/{filename}`` (e.g. ``core_behavior.md`` or ``tools/web_search/description.md``)."""
    ref = resources.files(_PROMPTS_PACKAGE).joinpath(filename)
    if not ref.is_file():
        return ""
    text = ref.read_text(encoding="utf-8")
    return text[:-1] if text.endswith("\n") else text
