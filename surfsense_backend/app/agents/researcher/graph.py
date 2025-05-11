from langgraph.graph import StateGraph
from .state import State
from .nodes import reformulate_user_query, write_answer_outline, process_sections
from .configuration import Configuration
from typing import TypedDict, List, Dict, Any, Optional

# Define what keys are in our state dict
class GraphState(TypedDict):
    # Intermediate data produced during workflow
    answer_outline: Optional[Any]
    # Final output
    final_written_report: Optional[str]

def build_graph():
    """
    Build and return the LangGraph workflow.
    
    This function constructs the researcher agent graph with proper state management
    and node connections following LangGraph best practices.
    
    Returns:
        A compiled LangGraph workflow
    """
    # Define a new graph with state class
    workflow = StateGraph(State, config_schema=Configuration)
    
    # Add nodes to the graph
    workflow.add_node("reformulate_user_query", reformulate_user_query)
    workflow.add_node("write_answer_outline", write_answer_outline)
    workflow.add_node("process_sections", process_sections)

    # Define the edges - create a linear flow
    workflow.add_edge("__start__", "reformulate_user_query")
    workflow.add_edge("reformulate_user_query", "write_answer_outline")
    workflow.add_edge("write_answer_outline", "process_sections")
    workflow.add_edge("process_sections", "__end__")

    # Compile the workflow into an executable graph
    graph = workflow.compile()
    graph.name = "Surfsense Researcher"  # This defines the custom name in LangSmith
    
    return graph

# Compile the graph once when the module is loaded
graph = build_graph()
