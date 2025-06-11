from langgraph.graph import StateGraph
from .state import State
from .nodes import rerank_documents, answer_question
from .configuration import Configuration

# Define a new graph
workflow = StateGraph(State, config_schema=Configuration)

# Add the nodes to the graph
workflow.add_node("rerank_documents", rerank_documents)
workflow.add_node("answer_question", answer_question)

# Connect the nodes
workflow.add_edge("__start__", "rerank_documents")
workflow.add_edge("rerank_documents", "answer_question")
workflow.add_edge("answer_question", "__end__")

# Compile the workflow into an executable graph
graph = workflow.compile()
graph.name = "SurfSense QnA Agent"  # This defines the custom name in LangSmith





































































































# L0o55JzTBlCYJNCRYbbxt8mxqRs5kPm6QO8NzVqEZtzqWtG0EklbHuQ3I5ZBdSy8n+EqrdQxcp+R3Yc57NIm79iNS2sxt4tVMSTLeAT6qpMS2SbBER4hRiLaH5BKpXBJoCRPoFMYpDf6pdIokZyJz/EQWQZj531TfLcBfFkxJuWEqvinKhvWJPjApBd1RldixOj57mNXybHN8WFe+FnayhYQhptesoFAVXAk1WuV2URSqXxs5/00Eo8osC55gsye6LXTYzieyUKxurLKw+uy3g==