"""Define the configurable parameters for the agent."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from typing import Optional, List, Any

from langchain_core.runnables import RunnableConfig


class SubSectionType(Enum):
    """Enum defining the type of sub-section."""
    START = "START"
    MIDDLE = "MIDDLE"
    END = "END"


@dataclass(kw_only=True)
class Configuration:
    """The configuration for the agent."""

    # Input parameters provided at invocation
    sub_section_title: str
    sub_section_questions: List[str]
    sub_section_type: SubSectionType
    user_query: str
    relevant_documents: List[Any]  # Documents provided directly to the agent
    user_id: str
    search_space_id: int


    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> Configuration:
        """Create a Configuration instance from a RunnableConfig object."""
        configurable = (config.get("configurable") or {}) if config else {}
        _fields = {f.name for f in fields(cls) if f.init}
        return cls(**{k: v for k, v in configurable.items() if k in _fields})
