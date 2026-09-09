import asyncio
import logging
import time
from collections.abc import AsyncIterator

from sqlalchemy.orm import Session

from modules.llm.models import ModelRole, SelectedModel
from modules.llm.providers import get_provider
from modules.llm.providers.types import Message
from shared.config import get_llm_settings
from worker.studio.artifact import Source
from worker.studio.builder import Builder

logger = logging.getLogger(__name__)


class NoModelSelectedError(RuntimeError):
    """No generation model is chosen, so the job cannot run."""


def generate(
    session: Session, builder: Builder, sources: list[Source], prompt: str | None
) -> str:
    """Run the selected generation model over the builder's prompt and sources.

    The builder owns the output contract (markdown for a summary, JSON for a
    structured format); this only routes it through the chosen Generator and
    collects the stream the worker cannot await lazily.
    """
    return run_model(session, builder.prompt(sources, prompt), sources)


def run_model(session: Session, system: str, sources: list[Source]) -> str:
    """Send one system prompt plus the grounding to the selected model.

    The shared core of every Studio generation: the builder path passes a
    builder's prompt, the code path passes its own. Both collect the stream the
    worker cannot await lazily.
    """
    selected = session.get(SelectedModel, ModelRole.GENERATION)
    if selected is None:
        raise NoModelSelectedError("no generation model selected")
    generator = get_provider(selected.provider, session)
    if generator is None:
        raise NoModelSelectedError(f"unknown provider: {selected.provider}")

    messages = [
        Message(role="system", content=system),
        Message(role="user", content=_grounding(sources)),
    ]
    started = time.monotonic()
    logger.info(
        "studio: model %s/%s starting (%s source chars) url=%s",
        selected.provider,
        selected.name,
        sum(len(source.content) for source in sources),
        get_llm_settings().ollama_base_url
        if selected.provider == "ollama"
        else selected.provider,
    )
    reply = asyncio.run(_collect(generator.chat(selected.name, messages)))
    logger.info(
        "studio: model %s/%s returned %s chars in %.1fs",
        selected.provider,
        selected.name,
        len(reply),
        time.monotonic() - started,
    )
    return reply


async def _collect(stream: AsyncIterator[str]) -> str:
    return "".join([delta async for delta in stream])


def _grounding(sources: list[Source]) -> str:
    if not sources:
        return "No sources were provided."
    return "\n\n".join(f"# {source.title}\n\n{source.content}" for source in sources)
