from collections.abc import Sequence

from modules.chat.models import ChatMessage
from modules.llm.providers.types import Message

# Prior turns are trimmed to fit this budget; the system message and the new user
# turn are pinned on top of it. A fraction of a small model's context window.
HISTORY_BUDGET_TOKENS = 3000


def build_messages(
    system: str, history: Sequence[ChatMessage], user_text: str
) -> list[Message]:
    """Assemble `[system, *recent history within budget, user]` for the generator."""
    turns = [Message(role=str(row.role.value), content=message_text(row)) for row in history]
    return [Message("system", system), *_within_budget(turns), Message("user", user_text)]


def message_text(row: ChatMessage) -> str:
    """The plain text of a stored turn; its citations are for the UI, not the model."""
    return row.content.get("text", "")


def _within_budget(turns: list[Message]) -> list[Message]:
    kept: list[Message] = []
    spent = 0
    for turn in reversed(turns):
        spent += _tokens(turn.content)
        if spent > HISTORY_BUDGET_TOKENS:
            break
        kept.append(turn)
    kept.reverse()
    return kept


def _tokens(text: str) -> int:
    # ponytail: ~4 chars per token dodges loading the model's tokenizer. Ceiling:
    # fine for a soft trim; swap in the real count if the runtime starts truncating.
    return len(text) // 4
