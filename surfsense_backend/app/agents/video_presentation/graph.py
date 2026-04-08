from langgraph.graph import StateGraph

from .configuration import Configuration
from .nodes import (
    assign_slide_themes,
    create_presentation_slides,
    create_slide_audio,
    generate_slide_scene_codes,
)
from .state import State


def build_graph():
    workflow = StateGraph(State, config_schema=Configuration)

    workflow.add_node("create_presentation_slides", create_presentation_slides)
    workflow.add_node("create_slide_audio", create_slide_audio)
    workflow.add_node("assign_slide_themes", assign_slide_themes)
    workflow.add_node("generate_slide_scene_codes", generate_slide_scene_codes)

    # Fan-out: after slides are parsed, run audio generation and theme
    # assignment in parallel (themes only need slide metadata, not audio).
    workflow.add_edge("__start__", "create_presentation_slides")
    workflow.add_edge("create_presentation_slides", "create_slide_audio")
    workflow.add_edge("create_presentation_slides", "assign_slide_themes")

    # Fan-in: scene code generation waits for both audio and themes.
    workflow.add_edge("create_slide_audio", "generate_slide_scene_codes")
    workflow.add_edge("assign_slide_themes", "generate_slide_scene_codes")

    workflow.add_edge("generate_slide_scene_codes", "__end__")

    graph = workflow.compile()
    graph.name = "Surfsense Video Presentation"

    return graph


graph = build_graph()
