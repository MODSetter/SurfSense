import asyncio
from collections.abc import AsyncIterator

from sqlalchemy.orm import Session

from modules.llm.models import ModelRole, SelectedModel
from modules.llm.providers import get_provider
from modules.llm.providers.types import Message
from worker.studio.builders import Builder, Source


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
    selected = session.get(SelectedModel, ModelRole.GENERATION)
    if selected is None:
        raise NoModelSelectedError("no generation model selected")
    generator = get_provider(selected.provider, session)
    if generator is None:
        raise NoModelSelectedError(f"unknown provider: {selected.provider}")

    messages = [
        Message(role="system", content=builder.prompt(sources, prompt)),
        Message(role="user", content=_grounding(sources)),
    ]
    return asyncio.run(_collect(generator.chat(selected.name, messages)))


async def _collect(stream: AsyncIterator[str]) -> str:
    return "".join([delta async for delta in stream])


def _grounding(sources: list[Source]) -> str:
    if not sources:
        return "No sources were provided."
    return "\n\n".join(f"# {source.title}\n\n{source.content}" for source in sources)
