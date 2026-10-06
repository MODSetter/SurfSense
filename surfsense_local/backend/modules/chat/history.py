from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from modules.chat.budget import (
    CHARS_PER_TOKEN,
    DEFAULT_HISTORY_TOKENS,
    HISTORY_HEADROOM,
    IMAGE_TOKENS,
)
from modules.chat.images import store
from modules.chat.models import ChatMessage, MessageRole
from modules.llm.providers.types import Image, Message

# A turn's exact cost by the model's own tokenizer, or None when it could not
# be counted (no endpoint, a transient failure). None falls back to the
# heuristic for that turn rather than being read as zero tokens.
TokenCounter = Callable[[str], Awaitable[int | None]]


@dataclass(frozen=True)
class ChatPrompt:
    """One turn's messages, and the stored message its history now starts at."""

    messages: list[Message]
    history_start_id: int | None


async def build_messages(
    system: str,
    history: Sequence[ChatMessage],
    user_text: str,
    *,
    excerpts: str | None = None,
    images: Sequence[Image] = (),
    history_budget: int = DEFAULT_HISTORY_TOKENS,
    token_count: TokenCounter | None = None,
    history_start_id: int | None = None,
) -> ChatPrompt:
    """Assemble `[system, *recent history within budget, user]` for the generator.

    `excerpts` go ahead of the new question and nowhere else, so the turns
    before it reach the model as they did last time and its cached prefix holds.

    `history_budget` defaults to today's fixed figure; a caller that knows the
    model's real window computes a tighter one with `modules.chat.budget` so
    the assembled prompt cannot outgrow it (see that module for why).

    `token_count` prices each turn exactly, by the model's own tokenizer,
    instead of the `~4 chars/token` estimate: only the local runtime can
    answer it, so a caller without one gets exactly today's heuristic trim.

    `history_start_id` is where the last turn's history started. History runs
    from there while it fits; past the budget it is cut, by whole exchanges, to
    `HISTORY_HEADROOM` under it, so the next turns start at the same message.
    """
    # One earlier picture at most rides along: the newest, so a follow-up about
    # it works, and none once this turn brings its own.
    history = _answered(history)
    resend = None if images else _newest_image_turn(history)
    turns = [
        (
            row.id,
            Message(
                role=str(row.role.value),
                content=message_text(row),
                images=_stored_images(row) if row is resend else (),
            ),
        )
        for row in history
        if history_start_id is None or row.id is None or row.id >= history_start_id
    ]
    budget = max(0, history_budget - IMAGE_TOKENS * len(images))
    kept, start_id = await _within_budget(turns, budget, token_count)
    # Labelled, or a short follow-up after the passages reads as being about the
    # last one: Qwen3 1.7B answered "And the X300?" about the X200 it named.
    question = f"{excerpts}\n\nQuestion: {user_text}" if excerpts else user_text
    messages = [
        Message("system", system),
        *kept,
        Message("user", question, images=tuple(images)),
    ]
    return ChatPrompt(messages, start_id if start_id is not None else history_start_id)


# Endings whose empty reply means the model never answered at all.
_UNANSWERED = frozenset({"error", "interrupted"})


def _answered(history: Sequence[ChatMessage]) -> list[ChatMessage]:
    """History without turns that failed before a word: an empty answer, or
    a question left with none, would only confuse the model."""
    kept: list[ChatMessage] = []
    for row in history:
        unanswered = (
            row.role is MessageRole.ASSISTANT
            and not message_text(row)
            and row.content.get("ending", {}).get("type") in _UNANSWERED
        )
        if not unanswered:
            kept.append(row)
        elif kept and kept[-1].role is MessageRole.USER:
            kept.pop()
    return kept


def message_text(row: ChatMessage) -> str:
    """The plain text of a stored turn; its citations are for the UI, not the model."""
    return row.content.get("text", "")


def _newest_image_turn(history: Sequence[ChatMessage]) -> ChatMessage | None:
    return next((row for row in reversed(history) if row.content.get("images")), None)


def _stored_images(row: ChatMessage) -> tuple[Image, ...]:
    """What is still on disk; a missing file leaves the turn as text."""
    loaded = (store.load(ref) for ref in row.content.get("images", []))
    return tuple(image for image in loaded if image is not None)


async def _within_budget(
    turns: list[tuple[int | None, Message]],
    budget: int,
    token_count: TokenCounter | None,
) -> tuple[list[Message], int | None]:
    """Every turn while they fit; past the budget, the newest whole exchanges
    that fit under its headroom, and the stored id of the first one kept."""
    costs: list[int] = []
    for _, turn in reversed(turns):
        images = IMAGE_TOKENS * len(turn.images)
        costs.append(await _cost(turn.content, token_count) + images)
        if sum(costs) > budget:
            break
    else:
        return [turn for _, turn in turns], None
    room = budget * (1 - HISTORY_HEADROOM)
    keep = 0
    while keep < len(costs) and sum(costs[: keep + 1]) <= room:
        keep += 1
    kept = turns[len(turns) - keep :] if keep else []
    # An exchange starts at its question; an answer alone answers nothing shown.
    while kept and kept[0][1].role != "user":
        kept = kept[1:]
    return [turn for _, turn in kept], kept[0][0] if kept else None


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
    return len(text) // CHARS_PER_TOKEN
