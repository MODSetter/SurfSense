"""What the eval sends for a case, built by chat's own code so it cannot drift."""

from chat_eval.cases import Case
from modules.chat.budget import ANSWER_RESERVE_TOKENS, history_budget
from modules.chat.history import build_messages
from modules.chat.models import ChatMessage, MessageRole
from modules.chat.prompt import build_context
from modules.llm.fit import CONTEXT_FLOOR_TOKENS
from modules.llm.profile import Tier
from modules.llm.providers.types import Message
from shared.search import Hit


async def conversation(case: Case, tier: Tier) -> list[Message]:
    """`[system, *history, question]`, assembled as chat assembles a turn.

    History is budgeted for the smallest window the app loads, so every machine
    and Featherless keep the same turns.
    """
    system, _ = build_context(_hits(case), tier)
    return await build_messages(
        system,
        _history(case),
        case.question,
        history_budget=history_budget(CONTEXT_FLOOR_TOKENS),
    )


def body(name: str, messages: list[Message], sampling: dict[str, float | int]) -> dict:
    """One request, unstreamed so the reply carries why it stopped."""
    return {
        "model": name,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "max_tokens": ANSWER_RESERVE_TOKENS,
        "stream": False,
        **sampling,
    }


def _hits(case: Case) -> list[Hit]:
    """The passages in rank order, so [n] is the nth. One title is one document."""
    documents: dict[str, int] = {}
    return [
        Hit(
            chunk_id=n,
            document_id=documents.setdefault(passage.title, len(documents) + 1),
            content=passage.text,
            start_line=None,
            end_line=None,
            score=1.0,
            title=passage.title,
        )
        for n, passage in enumerate(case.passages, start=1)
    ]


def _history(case: Case) -> list[ChatMessage]:
    """Prior turns as the stored rows chat reads its history from."""
    return [
        ChatMessage(role=MessageRole(turn.role), content={"text": turn.text})
        for turn in case.history
    ]
