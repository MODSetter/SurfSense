"""How much of a prompt the model reused rather than read again, as it reports.

Logged per reply, so a prompt that stopped matching its cached prefix shows up
as a number rather than as a slow answer nobody can explain. Nothing extra is
asked of an endpoint for it: a strict one rejects a field it does not know.
"""

import logging

logger = logging.getLogger(__name__)


def chunk_reuse(chunk: dict) -> tuple[int, int] | None:
    """Reused and total prompt tokens from a chat-completions chunk, if it says.

    llama-server's `timings` counts the two apart; an OpenAI-shaped `usage`
    counts the reused ones inside `prompt_tokens`.
    """
    timings = chunk.get("timings")
    if isinstance(timings, dict):
        reused, read = timings.get("cache_n"), timings.get("prompt_n")
        if isinstance(reused, int) and isinstance(read, int):
            return reused, reused + read
    usage = chunk.get("usage")
    if isinstance(usage, dict):
        details = usage.get("prompt_tokens_details")
        reused = details.get("cached_tokens") if isinstance(details, dict) else None
        total = usage.get("prompt_tokens")
        if isinstance(reused, int) and isinstance(total, int):
            return reused, total
    return None


def response_reuse(response: dict) -> tuple[int, int] | None:
    """Reused and total input tokens from a completed Responses API reply."""
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return None
    details = usage.get("input_tokens_details")
    reused = details.get("cached_tokens") if isinstance(details, dict) else None
    total = usage.get("input_tokens")
    if isinstance(reused, int) and isinstance(total, int):
        return reused, total
    return None


def log_reuse(model: str, reuse: tuple[int, int]) -> None:
    """One line per reply: how much of its prompt the model did not read again."""
    reused, total = reuse
    logger.info("%s reused %d of %d prompt tokens", model, reused, total)
