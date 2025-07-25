"""Define the state structures for the agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class State:
    """Defines the dynamic state for the Q&A agent during execution.

    This state tracks the database session, chat history, and the outputs
    generated by the agent's nodes during question answering.
    See: https://langchain-ai.github.io/langgraph/concepts/low_level/#state
    for more information.
    """

    # Runtime context
    db_session: AsyncSession

    chat_history: list[Any] | None = field(default_factory=list)
    # OUTPUT: Populated by agent nodes
    reranked_documents: list[Any] | None = None
    final_answer: str | None = None
