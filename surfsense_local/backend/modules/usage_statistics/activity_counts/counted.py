"""The counts the API's turn and plugin paths take: off the event loop, and never in the turn's way."""

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from api.dependencies import transact
from modules.chat.models import ChatThread
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.providers import llamacpp
from modules.usage_statistics.activity_counts.counts_file import (
    Activity,
    add,
    start_counting,
)
from modules.usage_statistics.activity_counts.tools_called import tools_called


def begin_counting(session: Session) -> None:
    """At startup: a library with no chat yet has missed nothing, so its counts are whole."""
    start_counting(had_chats=session.scalar(select(ChatThread.id).limit(1)) is not None)


def answer_kind(provider: str) -> Activity:
    """SurfSense's own llama.cpp is local; every connection is remote, even one on this machine."""
    if provider == llamacpp.PROVIDER:
        return Activity.LOCAL_ANSWER
    return Activity.REMOTE_ANSWER


async def count_chat_answer(provider: str) -> None:
    """A Basic chat reply the model wrote text for; the turn itself is already a chat_messages row."""
    await run_in_threadpool(add, {answer_kind(provider): 1})


async def count_agent_turn() -> None:
    """An Agentic turn its engine started; whether it was answered is counted when it ends."""
    await run_in_threadpool(add, {Activity.AGENT_TURN: 1})


async def count_agent_answer(session: Session) -> None:
    """An Agentic reply that ended with text, by the kind the selected text model is."""
    provider = await transact(session, _selected_text_provider)
    if provider is not None:
        await run_in_threadpool(add, {answer_kind(provider): 1})


async def count_plugin_calls(body: bytes) -> None:
    """The tool calls one MCP request to a plugin's server carries."""
    calls = tools_called(body)
    if calls:
        await run_in_threadpool(add, {Activity.PLUGIN_CALL: calls})


def _selected_text_provider(session: Session) -> str | None:
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    return None if selected is None else selected.provider
