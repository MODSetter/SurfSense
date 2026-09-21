from collections.abc import Awaitable, Callable, Sequence

from modules.chat.budget import DEFAULT_HISTORY_TOKENS
from modules.chat.models import ChatMessage
from modules.llm.providers.types import Message

# A turn's exact cost by the model's own tokenizer, or None when it could not
# be counted (no endpoint, a transient failure). None falls back to the
# heuristic for that turn rather than being read as zero tokens.
TokenCounter = Callable[[str], Awaitable[int | None]]


async def build_messages(
    system: str,
    history: Sequence[ChatMessage],
    user_text: str,
    *,
    history_budget: int = DEFAULT_HISTORY_TOKENS,
    token_count: TokenCounter | None = None,
) -> list[Message]:
    """Assemble `[system, *recent history within budget, user]` for the generator.

    `history_budget` defaults to today's fixed figure; a caller that knows the
    model's real window computes a tighter one with `modules.chat.budget` so
    the assembled prompt cannot outgrow it (see that module for why).

    `token_count` prices each turn exactly, by the model's own tokenizer,
    instead of the `~4 chars/token` estimate: only the local runtime can
    answer it, so a caller without one gets exactly today's heuristic trim.
    """
    turns = [Message(role=str(row.role.value), content=message_text(row)) for row in history]
    kept = await _within_budget(turns, history_budget, token_count)
    return [Message("system", system), *kept, Message("user", user_text)]


def message_text(row: ChatMessage) -> str:
    """The plain text of a stored turn; its citations are for the UI, not the model."""
    return row.content.get("text", "")


async def _within_budget(
    turns: list[Message], budget: int, token_count: TokenCounter | None
) -> list[Message]:
    kept: list[Message] = []
    spent = 0
    for turn in reversed(turns):
        spent += await _cost(turn.content, token_count)
        if spent > budget:
            break
        kept.append(turn)
    kept.reverse()
    return kept


async def _cost(text: str, token_count: TokenCounter | None) -> int:
    """A turn's price: exact when a counter is given and answers, the
    heuristic otherwise. Never mixes the two within one turn."""
    if token_count is not None:
        exact = await token_count(text)
        if exact is not None:
            return exact
    return _tokens(text)


def _tokens(text: str) -> int:
    # ponytail: ~4 chars per token dodges loading the model's tokenizer. Ceiling:
    # fine for a soft trim; swap in the real count if the runtime starts truncating.
    return len(text) // 4
