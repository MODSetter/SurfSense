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


class ChatThread(Base):
    __tablename__ = "chat_threads"
    __table_args__ = (Index("chat_threads_workspace", "workspace_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    title: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped[Workspace] = relationship(back_populates="chat_threads")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan"
    )


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

    thread: Mapped[ChatThread] = relationship(back_populates="messages")
