"""Which engine a new thread gets: the agent for a tested model, the chat for every other.

docs/proposals/agent/01-which-engine.md. A thread keeps what it got.
"""

from sqlalchemy.orm import Session

from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from shared.config import get_agent_settings

# Models that passed the agent's test at a window of 32,768 tokens or more.
TESTED_MODELS: frozenset[str] = frozenset()


def agent_answers(session: Session) -> bool:
    """Whether a thread opened now, with the model selected now, should be the agent's."""
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is None:
        return False
    return selected.name in TESTED_MODELS or get_agent_settings().agent_untested_models
