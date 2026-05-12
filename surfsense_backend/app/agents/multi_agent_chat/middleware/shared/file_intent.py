"""File-intent classifier that gates strict write contracts."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.agents.new_chat.middleware import FileIntentMiddleware


def build_file_intent_mw(llm: BaseChatModel) -> FileIntentMiddleware:
    return FileIntentMiddleware(llm=llm)
