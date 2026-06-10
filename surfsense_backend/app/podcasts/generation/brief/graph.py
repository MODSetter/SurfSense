"""The brief-planning graph: detect language, then propose a spec."""

from __future__ import annotations

from langgraph.graph import StateGraph

from .config import BriefConfig
from .nodes import detect_language, propose_spec
from .state import BriefState


def build_brief_graph():
    workflow = StateGraph(BriefState, config_schema=BriefConfig)

    workflow.add_node("detect_language", detect_language)
    workflow.add_node("propose_spec", propose_spec)

    workflow.add_edge("__start__", "detect_language")
    workflow.add_edge("detect_language", "propose_spec")
    workflow.add_edge("propose_spec", "__end__")

    graph = workflow.compile()
    graph.name = "Surfsense Podcast Brief"
    return graph


graph = build_brief_graph()
