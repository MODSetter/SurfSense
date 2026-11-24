"""How much of the model's window a Studio job's sources may fill, priced in tokens."""

import math
from collections.abc import Callable

from modules.artifacts.studio_documents.window import CAPTION_CHARS, FIGURE_LINE_CHARS
from modules.llm.admission.cost import MESSAGE_OVERHEAD_TOKENS, text_tokens
from worker.studio.shared.artifact import Source
from worker.studio.shared.gather import BUDGET_CHARS, MIN_SHARE_CHARS
from worker.studio.shared.generate import grounding_text

# Admission's price for Latin text, so the first budget in characters is three a token.
CHARS_PER_TOKEN = 3
# The longest system prompt a draft sends but a written web page's: a deck's
# script prompt at the frontier tier, 3,410 characters with its skill.
PROMPT_TOKENS = 1_200
# The system prompt and the sources, and a repair's two turns after them.
MESSAGES = 4
# The reply shares the window, so a quarter is kept: 2,048 tokens at the 8,192
# floor a local model loads at, for the 10 questions or 20 cards a compact prompt
# asks there (Qwen3 4B wrote them in about 1,100 and 1,500).
REPLY_SHARE = 0.25
# The estimate is not the model's tokenizer, and a chat template adds words of its own.
MARGIN_SHARE = 0.1
# Less room than about one chunk of text would ground the job on nothing.
MIN_SOURCE_TOKENS = MIN_SHARE_CHARS // CHARS_PER_TOKEN
# Gathers before giving up: each cuts the text by what the last one overran.
TRIES = 3

DOES_NOT_FIT = (
    "The selected sources don't fit the model's context window. Select fewer "
    "sources, or choose a model with a larger context window."
)


class SourcesDoNotFitError(RuntimeError):
    """The window cannot hold the sources; asking again would fail the same way."""


def sources_room(window: int | None, focus: str | None) -> int | None:
    """The tokens the sources may take, or None for a window nothing states."""
    if window is None:
        return None
    room = (
        window
        - PROMPT_TOKENS
        - text_tokens(focus or "")
        - MESSAGES * MESSAGE_OVERHEAD_TOKENS
        - math.ceil(window * REPLY_SHARE)
        - math.ceil(window * MARGIN_SHARE)
    )
    if room < MIN_SOURCE_TOKENS:
        raise SourcesDoNotFitError(
            f"The model's context window, {window:,} tokens, is too small to hold "
            "any of the sources. Choose a model with a larger context window."
        )
    return room


def fit_sources(
    gather_within: Callable[[int | None], list[Source]], room: int | None
) -> list[Source]:
    """The sources gathered at a character budget, cut again while they cost more
    tokens than the room: Chinese runs near a token a character, not three."""
    if room is None:
        return gather_within(None)
    budget = min(BUDGET_CHARS, room * CHARS_PER_TOKEN)
    for _ in range(TRIES):
        sources = gather_within(budget)
        cost = text_tokens(grounding_text(sources)) + _figure_list_tokens(sources)
        if cost <= room:
            return sources
        text = "".join(source.content for source in sources)
        if not text:
            break
        text_cost = text_tokens(text)
        # The titles, breaks and figure list stay; the text gives way at its own density.
        budget = math.floor(len(text) * (room - (cost - text_cost)) / text_cost)
        if budget < 1:
            break
    raise SourcesDoNotFitError(DOES_NOT_FIT)


def _figure_list_tokens(sources: list[Source]) -> int:
    """The list a Word or PDF draft's prompt gives of the figures it may place."""
    captions = [
        " ".join((figure.caption or "").split())[:CAPTION_CHARS]
        for source in sources
        for figure in source.figures
    ]
    line = math.ceil(FIGURE_LINE_CHARS / CHARS_PER_TOKEN)
    return sum(text_tokens(caption) + line for caption in captions)
