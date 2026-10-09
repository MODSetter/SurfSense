"""The two ways a chat can answer, chosen when it starts and kept."""

from enum import StrEnum

__all__ = ["ChatMode"]


class ChatMode(StrEnum):
    # The chat engine: retrieval Q&A, with Studio beside it.
    BASIC = "basic"
    # The agent engine, opencode, working through steps and tools.
    AGENTIC = "agentic"
