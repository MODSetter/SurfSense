"""Guardrail: the multi-engine ``web_search`` tool is fully retired.

Public web search now runs exclusively through the ``google_search`` subagent,
and the four search connector types (Tavily/SearXNG/Linkup/Baidu) are soft-
deprecated. This pins those invariants so a future change can't quietly bring
the ``web_search`` tool back or un-deprecate a search connector.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.agents.chat.multi_agent_chat.main_agent.tools.index import (
    MAIN_AGENT_SURFSENSE_TOOL_NAMES,
)
from app.agents.chat.multi_agent_chat.subagents.registry import (
    SUBAGENT_BUILDERS_BY_NAME,
)
from app.utils.validators import DEPRECATED_CONNECTOR_TYPES, raise_if_connector_deprecated

pytestmark = pytest.mark.unit

_DEPRECATED_SEARCH_TYPES = (
    "TAVILY_API",
    "SEARXNG_API",
    "LINKUP_API",
    "BAIDU_SEARCH_API",
)


def test_web_search_tool_removed_from_main_agent():
    assert "web_search" not in MAIN_AGENT_SURFSENSE_TOOL_NAMES


def test_google_search_specialist_present():
    assert "google_search" in SUBAGENT_BUILDERS_BY_NAME


@pytest.mark.parametrize("connector_type", _DEPRECATED_SEARCH_TYPES)
def test_search_connectors_deprecated(connector_type):
    assert connector_type in DEPRECATED_CONNECTOR_TYPES
    with pytest.raises(HTTPException) as excinfo:
        raise_if_connector_deprecated(connector_type)
    assert excinfo.value.status_code == 410
