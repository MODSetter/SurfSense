"""What a refresh loses, so a bad upstream day never ships unread."""

from typing import Any

__all__ = ["MAX_MODEL_LOSS", "shrinkage"]

# Providers retire models every week, so some loss is ordinary. A fifth of the
# catalogue at once is an upstream outage or a broken fetch, not a retirement.
MAX_MODEL_LOSS = 0.2


def shrinkage(previous: dict[str, Any], proposed: dict[str, Any]) -> list[str]:
    """Why this refresh needs a person's say-so. Empty means it does not."""
    before = previous["providers"]
    after = proposed["providers"]
    problems = [f"provider {name} disappeared" for name in sorted(set(before) - set(after))]

    count_before = sum(len(provider["models"]) for provider in before.values())
    count_after = sum(len(provider["models"]) for provider in after.values())
    if count_before and (count_before - count_after) / count_before > MAX_MODEL_LOSS:
        problems.append(f"models fell from {count_before} to {count_after}")
    return problems
