"""The transcript-drafting graph: outline, draft segments, finalize."""

from __future__ import annotations

from langgraph.graph import StateGraph

from .config import TranscriptConfig
from .nodes import draft_segments, finalize, plan_outline
from .state import TranscriptState


def build_transcript_graph():
    workflow = StateGraph(TranscriptState, config_schema=TranscriptConfig)

    workflow.add_node("plan_outline", plan_outline)
    workflow.add_node("draft_segments", draft_segments)
    workflow.add_node("finalize", finalize)

    workflow.add_edge("__start__", "plan_outline")
    workflow.add_edge("plan_outline", "draft_segments")
    workflow.add_edge("draft_segments", "finalize")
    workflow.add_edge("finalize", "__end__")

    graph = workflow.compile()
    graph.name = "Surfsense Podcast Transcript"
    return graph


graph = build_transcript_graph()
