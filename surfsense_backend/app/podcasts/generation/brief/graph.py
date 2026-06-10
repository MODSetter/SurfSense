"""The brief-planning graph: propose a reviewable spec from defaults."""

from __future__ import annotations

from langgraph.graph import StateGraph

from .config import BriefConfig
from .nodes import propose_spec
from .state import BriefState


def build_brief_graph():
    workflow = StateGraph(BriefState, config_schema=BriefConfig)

    workflow.add_node("propose_spec", propose_spec)

    workflow.add_edge("__start__", "propose_spec")
    workflow.add_edge("propose_spec", "__end__")

    graph = workflow.compile()
    graph.name = "Surfsense Podcast Brief"
    return graph


graph = build_brief_graph()
