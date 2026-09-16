"""The system prompt that asks the model to write one format's builder code."""

from __future__ import annotations

from modules.llm import prompting
from modules.llm.profile import Tier
from worker.studio.office.spec import Office


def build(tier: Tier, spec: Office, user_prompt: str | None) -> str:
    """The prompt for `spec`: the contract, its authoring skill, any emphasis."""
    return prompting.load(
        __package__,
        tier,
        focus=prompting.focus(user_prompt),
        label=spec.label,
        library=spec.library,
        skill=spec.skill,
    )
