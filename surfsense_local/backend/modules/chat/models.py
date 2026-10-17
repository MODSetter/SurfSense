import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules.workspaces.models import Workspace
from shared.db import Base, text_enum


class MessageRole(enum.StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AgentEngineKind(enum.StrEnum):
    OPENCODE = "opencode"
    CLAUDE_CODE = "claude_code"


class ChatThread(Base):
    __tablename__ = "chat_threads"
    __table_args__ = (
        Index("chat_threads_workspace", "workspace_id"),
        Index("chat_threads_cloud_id", "cloud_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    # The hosted thread this one was imported from, so a re-import finds it.
    cloud_id: Mapped[int | None]
    title: Mapped[str | None]
    # The engine whose session holds this thread's turns, not chat_messages;
    # None for a chat thread. Chosen when the thread is opened.
    agent_engine: Mapped[AgentEngineKind | None] = mapped_column(
        text_enum(AgentEngineKind)
    )
    # The thread's opencode session, once opencode has run it.
    opencode_session_id: Mapped[str | None]
    # The thread's Claude Code session, chosen when Claude Code first runs it.
    claude_session_id: Mapped[str | None]
    # A digest of the Claude account that session runs under: another account gets a new one.
    claude_account: Mapped[str | None]
    # The sources the user ticked, resolved on the server per turn; None is all.
    source_scope: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # The oldest message the model is still sent once history was trimmed. Kept
    # so the next turn starts there too: the runtime reuses a prompt only up to
    # its first changed token.
    history_start_message_id: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped[Workspace] = relationship(back_populates="chat_threads")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def uses_agent(self) -> bool:
        """Whether the agent answers this thread rather than the chat."""
        return self.agent_engine is not None


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (Index("chat_messages_thread", "chat_thread_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_thread_id: Mapped[int] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE")
    )
    role: Mapped[MessageRole] = mapped_column(text_enum(MessageRole))
    # Parts and citations travel together; only the UI interprets the shape.
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None]

    thread: Mapped[ChatThread] = relationship(back_populates="messages")
