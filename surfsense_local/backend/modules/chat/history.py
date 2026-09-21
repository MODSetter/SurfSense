from collections.abc import Sequence

from modules.chat.budget import DEFAULT_HISTORY_TOKENS
from modules.chat.models import ChatMessage
from modules.llm.providers.types import Message


def build_messages(
    system: str,
    history: Sequence[ChatMessage],
    user_text: str,
    *,
    history_budget: int = DEFAULT_HISTORY_TOKENS,
) -> list[Message]:
    """Assemble `[system, *recent history within budget, user]` for the generator.

    `history_budget` defaults to today's fixed figure; a caller that knows the
    model's real window computes a tighter one with `modules.chat.budget` so
    the assembled prompt cannot outgrow it (see that module for why).
    """
    turns = [Message(role=str(row.role.value), content=message_text(row)) for row in history]
    return [Message("system", system), *_within_budget(turns, history_budget), Message("user", user_text)]


def message_text(row: ChatMessage) -> str:
    """The plain text of a stored turn; its citations are for the UI, not the model."""
    return row.content.get("text", "")


def _within_budget(turns: list[Message], budget: int) -> list[Message]:
    kept: list[Message] = []
    spent = 0
    for turn in reversed(turns):
        spent += _tokens(turn.content)
        if spent > budget:
            break
        kept.append(turn)
    kept.reverse()
    return kept


def _tokens(text: str) -> int:
    # ponytail: ~4 chars per token dodges loading the model's tokenizer. Ceiling:
    # fine for a soft trim; swap in the real count if the runtime starts truncating.
    return len(text) // 4
