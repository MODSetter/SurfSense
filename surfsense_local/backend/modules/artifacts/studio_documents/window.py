"""Whether a spec fits the selected model's window to be rewritten whole in one call."""

import math
from dataclasses import dataclass

# The estimate chat prices text with when no tokenizer is asked (modules/chat/budget.py).
CHARS_PER_TOKEN = 4
# The refine prompt with its rules, rounded up; the list of figures is counted apart.
PROMPT_TOKENS = 1_500
# The rewrite may come back longer than it went in.
GROWTH = 1.25
# What the prompt keeps of a figure's caption, and the name and punctuation
# around it on its line (worker/studio/office/document/figure_list.py).
CAPTION_CHARS = 200
FIGURE_LINE_CHARS = 40


def figure_list_chars(captions: list[str | None]) -> int:
    """About how long the prompt's list of the figures the document may place is."""
    return sum(
        min(len(" ".join((caption or "").split())), CAPTION_CHARS) + FIGURE_LINE_CHARS
        for caption in captions
    )


@dataclass(frozen=True)
class TooLong:
    """A rewrite that does not fit, as the numbers its sentence is made of."""

    model: str
    spec_tokens: int
    needed_tokens: int
    window_tokens: int

    @property
    def reason(self) -> str:
        return (
            f"This document is too long for {self.model} to rewrite in one go: it is "
            f"about {self.spec_tokens:,} tokens, and reading it and writing it again "
            f"needs about {self.needed_tokens:,} of the model's "
            f"{self.window_tokens:,}-token window."
        )


def too_long(
    spec: str, instruction: str, model: str, window: int, figures_chars: int = 0
) -> TooLong | None:
    """Why the rewrite cannot fit: the model reads the spec and writes it again."""
    spec_tokens = math.ceil(len(spec) / CHARS_PER_TOKEN)
    needed = (
        PROMPT_TOKENS
        + math.ceil(figures_chars / CHARS_PER_TOKEN)
        + math.ceil(len(instruction) / CHARS_PER_TOKEN)
        + spec_tokens
        + math.ceil(spec_tokens * GROWTH)
    )
    if needed <= window:
        return None
    return TooLong(model, spec_tokens, needed, window)
