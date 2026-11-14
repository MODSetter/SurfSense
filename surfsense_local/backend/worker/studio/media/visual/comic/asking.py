"""Asking the chat model for the comic's plan, once more if its reply is not one."""

import logging

from modules.artifacts.comic.kinds import Kind
from modules.llm.resolution import ResolvedGeneration
from worker.studio.media.visual.comic import plan as planning
from worker.studio.media.visual.comic.schema import REPLY
from worker.studio.shared import generate
from worker.studio.shared.artifact import Source

logger = logging.getLogger(__name__)

# Enough of a reply to tell a refusal from broken JSON in the log.
_LOGGED_CHARS = 500


def ask_for_plan(
    writer: ResolvedGeneration,
    sources: list[Source],
    user_prompt: str | None,
    kind: Kind,
    count: int,
    untitled: str,
) -> planning.Plan:
    """Nothing is drawn yet, so a second ask costs one text reply, not pages."""
    system = planning.prompt(writer.tier, user_prompt, kind, count)
    reply = generate.run_model(writer, system, sources, json_schema=REPLY)
    try:
        return planning.parse(reply, untitled, count)
    except ValueError as first:
        first_error = first
        logger.warning(
            "studio: comic plan unreadable (%s); asking again. It began: %r",
            first,
            reply[:_LOGGED_CHARS],
        )
    retry = generate.run_model(
        writer,
        system,
        sources,
        json_schema=REPLY,
        repair=generate.Repair(
            reply,
            f"Your previous reply could not be used: {first_error}. Return only "
            f"the plan as one JSON object, with exactly {count} pages.",
        ),
    )
    try:
        return planning.parse(retry, untitled, count)
    except ValueError as error:
        logger.warning("studio: comic plan unreadable again: %r", retry[:_LOGGED_CHARS])
        raise _unplanned(retry, error) from error


def _unplanned(reply: str, error: ValueError) -> ValueError:
    """A reply with no JSON in it is the model saying no; the user reads its words."""
    said = next((line.strip() for line in reply.splitlines() if line.strip()), "")
    if said and "{" not in reply:
        return ValueError(f"The model did not plan the comic. It said: {said}")
    return ValueError(f"The model's comic plan could not be read: {error}")
