import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from modules.llm.providers.types import Message
from modules.llm.resolution import ResolvedGeneration
from worker.studio.shared import cancellation
from worker.studio.shared.artifact import Source

logger = logging.getLogger(__name__)

# How long a cancel may wait for the model to be hung up on.
CANCEL_POLL_SECONDS = 1.0


@dataclass(frozen=True)
class Repair:
    """The reply that failed and what to tell the model about it."""

    reply: str
    instruction: str


def run_model(
    model: ResolvedGeneration,
    system: str,
    sources: list[Source],
    *,
    repair: Repair | None = None,
) -> str:
    """Send one system prompt plus the grounding to the chosen generation model.

    Every kind that asks the model to write (content, web, office, podcast) goes
    through here; each collects the stream the worker cannot await lazily.

    A retry passes `repair`, which replays the failed reply as the model's own
    turn before asking for the correction. Without it an error naming a line
    points at a script the model was never shown, so it can only start over.
    """
    selected = model.selection
    messages = [
        Message(role="system", content=system),
        Message(role="user", content=_grounding(sources)),
    ]
    if repair is not None:
        messages += [
            Message(role="assistant", content=repair.reply),
            Message(role="user", content=repair.instruction),
        ]
    started = time.monotonic()
    logger.info(
        "studio: model %s/%s starting on the %s prompt (%s source chars)",
        selected.provider,
        selected.name,
        model.tier,
        sum(len(source.content) for source in sources),
    )
    # Thinking off: a small model can reason until the window runs out, holding
    # the runtime's only slot, and Studio's structured output gains little.
    reply = asyncio.run(
        _collect(model.generator.chat(selected.name, messages, reasoning=False))
    )
    logger.info(
        "studio: model %s/%s returned %s chars in %.1fs",
        selected.provider,
        selected.name,
        len(reply),
        time.monotonic() - started,
    )
    return reply


async def _collect(stream: AsyncIterator[str]) -> str:
    """The whole reply, or a cancel within a poll of it being asked for.

    Abandoning the read closes the request, which is what stops the model;
    polling on a timer rather than per token also covers a long prompt read,
    when no token has arrived yet.
    """
    reading = asyncio.ensure_future(_join(stream))
    while True:
        done, _ = await asyncio.wait({reading}, timeout=CANCEL_POLL_SECONDS)
        if done:
            return reading.result()
        try:
            cancellation.raise_if_cancelled()
        except BaseException:
            reading.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reading
            raise


async def _join(stream: AsyncIterator[str]) -> str:
    return "".join([delta async for delta in stream])


def _grounding(sources: list[Source]) -> str:
    if not sources:
        return "No sources were provided."
    return "\n\n".join(f"# {source.title}\n\n{source.content}" for source in sources)
