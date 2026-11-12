"""How many cards or questions a small model is asked for and held to.

Left to stop on its own, Qwen3 0.6B closed a deck after one card, while Qwen3 4B
wrote exactly the count it was asked for. So the small prompt states a count
the sources can carry, and the grammar holds the model to it.
"""

from modules.llm.profile import Tier
from worker.studio.shared.artifact import Source


def asked_count(sources: list[Source], ceiling: int, chars_per_item: int) -> int:
    """One item per `chars_per_item` of source text, at least one, at most `ceiling`."""
    chars = sum(len(source.content) for source in sources)
    return max(1, min(ceiling, chars // chars_per_item))


def least_count(tier: Tier, asked: int) -> int:
    """The fewest items the grammar allows. A larger model's prompt leaves the
    count to the material, so it is never padded to one."""
    return asked if tier is Tier.COMPACT else 1
