from langgraph.graph import StateGraph
from .state import State
from .nodes import fetch_relevant_documents, write_sub_section
from .configuration import Configuration

# Define a new graph
workflow = StateGraph(State, config_schema=Configuration)

# Add the nodes to the graph
workflow.add_node("fetch_relevant_documents", fetch_relevant_documents)
workflow.add_node("write_sub_section", write_sub_section)

# Entry point
workflow.add_edge("__start__", "fetch_relevant_documents")
# Connect fetch_relevant_documents to write_sub_section
workflow.add_edge("fetch_relevant_documents", "write_sub_section")
# Exit point
workflow.add_edge("write_sub_section", "__end__")

# Compile the workflow into an executable graph
graph = workflow.compile()
graph.name = "Sub Section Writer"  # This defines the custom name in LangSmith
