"""Define the configurable parameters for the agent."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from typing import Optional, List, Any

from langchain_core.runnables import RunnableConfig

class SearchMode(Enum): 
    """Enum defining the type of search mode."""
    CHUNKS = "CHUNKS"
    DOCUMENTS = "DOCUMENTS"

class ResearchMode(Enum):
    """Enum defining the type of research mode."""
    QNA = "QNA"
    REPORT_GENERAL = "REPORT_GENERAL"
    REPORT_DEEP = "REPORT_DEEP"
    REPORT_DEEPER = "REPORT_DEEPER"


@dataclass(kw_only=True)
class Configuration:
    """The configuration for the agent."""

    # Input parameters provided at invocation
    user_query: str
    num_sections: int
    connectors_to_search: List[str]
    user_id: str
    search_space_id: int
    search_mode: SearchMode
    research_mode: ResearchMode
    document_ids_to_add_in_context: List[int]

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> Configuration:
        """Create a Configuration instance from a RunnableConfig object."""
        configurable = (config.get("configurable") or {}) if config else {}
        _fields = {f.name for f in fields(cls) if f.init}
        return cls(**{k: v for k, v in configurable.items() if k in _fields})
