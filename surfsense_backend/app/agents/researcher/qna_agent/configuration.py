"""Define the configurable parameters for the agent."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Optional, List, Any

from langchain_core.runnables import RunnableConfig


@dataclass(kw_only=True)
class Configuration:
    """The configuration for the Q&A agent."""

    # Configuration parameters for the Q&A agent
    user_query: str  # The user's question to answer
    reformulated_query: str  # The reformulated query
    relevant_documents: List[Any]  # Documents provided directly to the agent for answering
    user_id: str  # User identifier
    search_space_id: int  # Search space identifier

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> Configuration:
        """Create a Configuration instance from a RunnableConfig object."""
        configurable = (config.get("configurable") or {}) if config else {}
        _fields = {f.name for f in fields(cls) if f.init}
        return cls(**{k: v for k, v in configurable.items() if k in _fields})
