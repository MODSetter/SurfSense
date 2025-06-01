from langgraph.graph import StateGraph

from .configuration import Configuration
from .state import State


from .nodes import create_merged_podcast_audio, create_podcast_transcript


def build_graph():
    
    # Define a new graph
    workflow = StateGraph(State, config_schema=Configuration)

    # Add the node to the graph
    workflow.add_node("create_podcast_transcript", create_podcast_transcript)
    workflow.add_node("create_merged_podcast_audio", create_merged_podcast_audio)

    # Set the entrypoint as `call_model`
    workflow.add_edge("__start__", "create_podcast_transcript")
    workflow.add_edge("create_podcast_transcript", "create_merged_podcast_audio")
    workflow.add_edge("create_merged_podcast_audio", "__end__")

    # Compile the workflow into an executable graph
    graph = workflow.compile()
    graph.name = "Surfsense Podcaster"  # This defines the custom name in LangSmith
    
    return graph

# Compile the graph once when the module is loaded
graph = build_graph()
