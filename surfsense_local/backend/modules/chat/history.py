from collections.abc import Awaitable, Callable, Sequence

from modules.chat.budget import CHARS_PER_TOKEN, DEFAULT_HISTORY_TOKENS, IMAGE_TOKENS
from modules.chat.images import store
from modules.chat.models import ChatMessage
from modules.llm.providers.types import Image, Message

# A turn's exact cost by the model's own tokenizer, or None when it could not
# be counted (no endpoint, a transient failure). None falls back to the
# heuristic for that turn rather than being read as zero tokens.
TokenCounter = Callable[[str], Awaitable[int | None]]


async def build_messages(
    system: str,
    history: Sequence[ChatMessage],
    user_text: str,
    *,
    excerpts: str | None = None,
    images: Sequence[Image] = (),
    history_budget: int = DEFAULT_HISTORY_TOKENS,
    token_count: TokenCounter | None = None,
) -> list[Message]:
    """Assemble `[system, *recent history within budget, user]` for the generator.

    `excerpts` go ahead of the new question and nowhere else, so the turns
    before it reach the model as they did last time and its cached prefix holds.

    `history_budget` defaults to today's fixed figure; a caller that knows the
    model's real window computes a tighter one with `modules.chat.budget` so
    the assembled prompt cannot outgrow it (see that module for why).

    `token_count` prices each turn exactly, by the model's own tokenizer,
    instead of the `~4 chars/token` estimate: only the local runtime can
    answer it, so a caller without one gets exactly today's heuristic trim.
    """
    # One earlier picture at most rides along: the newest, so a follow-up about
    # it works, and none once this turn brings its own.
    resend = None if images else _newest_image_turn(history)
    turns = [
        Message(
            role=str(row.role.value),
            content=message_text(row),
            images=_stored_images(row) if row is resend else (),
        )
        for row in history
    ]
    budget = max(0, history_budget - IMAGE_TOKENS * len(images))
    kept = await _within_budget(turns, budget, token_count)
    question = f"{excerpts}\n\n{user_text}" if excerpts else user_text
    return [
        Message("system", system),
        *kept,
        Message("user", question, images=tuple(images)),
    ]


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
    turns: list[Message], budget: int, token_count: TokenCounter | None
) -> list[Message]:
    kept: list[Message] = []
    spent = 0
    for turn in reversed(turns):
        images = IMAGE_TOKENS * len(turn.images)
        spent += await _cost(turn.content, token_count) + images
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
    return len(text) // CHARS_PER_TOKEN
