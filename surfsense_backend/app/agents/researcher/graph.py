from langgraph.graph import StateGraph

from .configuration import Configuration
from .nodes import (
    generate_further_questions,
    handle_qna_workflow,
    reformulate_user_query,
)
from .state import State


def build_graph():
    """
    Build and return the LangGraph workflow.

    This function constructs the researcher agent graph for Q&A workflow.
    The workflow follows a simple path:
    1. Reformulate user query based on chat history
    2. Handle QNA workflow (fetch documents and generate answer)
    3. Generate follow-up questions

    Returns:
        A compiled LangGraph workflow
    """
    # Define a new graph with state class
    workflow = StateGraph(State, config_schema=Configuration)

    # Add nodes to the graph
    workflow.add_node("reformulate_user_query", reformulate_user_query)
    workflow.add_node("handle_qna_workflow", handle_qna_workflow)
    workflow.add_node("generate_further_questions", generate_further_questions)

    # Define the edges - simple linear flow for QNA
    workflow.add_edge("__start__", "reformulate_user_query")
    workflow.add_edge("reformulate_user_query", "handle_qna_workflow")
    workflow.add_edge("handle_qna_workflow", "generate_further_questions")
    workflow.add_edge("generate_further_questions", "__end__")

    # Compile the workflow into an executable graph
    graph = workflow.compile()
    graph.name = "Surfsense Researcher"  # This defines the custom name in LangSmith

    return graph


# Compile the graph once when the module is loaded
graph = build_graph()
