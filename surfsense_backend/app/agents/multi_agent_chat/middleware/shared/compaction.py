"""Context-window summarization with SurfSense protected sections."""

from __future__ import annotations

from typing import Any

from deepagents.backends import StateBackend
from langchain_core.language_models import BaseChatModel

from app.agents.new_chat.middleware import create_surfsense_compaction_middleware


def build_compaction_mw(llm: BaseChatModel) -> Any:
    return create_surfsense_compaction_middleware(llm, StateBackend)
