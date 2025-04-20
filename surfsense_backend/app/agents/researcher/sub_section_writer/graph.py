from langgraph.graph import StateGraph
from .state import State
from .nodes import write_sub_section, rerank_documents
from .configuration import Configuration

# Define a new graph
workflow = StateGraph(State, config_schema=Configuration)

# Add the nodes to the graph
workflow.add_node("rerank_documents", rerank_documents)
workflow.add_node("write_sub_section", write_sub_section)

# Connect the nodes
workflow.add_edge("__start__", "rerank_documents")
workflow.add_edge("rerank_documents", "write_sub_section")
workflow.add_edge("write_sub_section", "__end__")

# Compile the workflow into an executable graph
graph = workflow.compile()
graph.name = "Sub Section Writer"  # This defines the custom name in LangSmith
