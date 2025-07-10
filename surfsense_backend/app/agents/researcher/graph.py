from langgraph.graph import StateGraph
from .state import State
from .nodes import reformulate_user_query, write_answer_outline, process_sections, handle_qna_workflow, generate_further_questions
from .configuration import Configuration, ResearchMode
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
    
    This function constructs the researcher agent graph with conditional routing
    based on research_mode - QNA mode uses a direct Q&A workflow while other modes
    use the full report generation pipeline. Both paths generate follow-up questions
    at the end using the reranked documents from the sub-agents.
    
    Returns:
        A compiled LangGraph workflow
    """
    # Define a new graph with state class
    workflow = StateGraph(State, config_schema=Configuration)
    
    # Add nodes to the graph
    workflow.add_node("reformulate_user_query", reformulate_user_query)
    workflow.add_node("handle_qna_workflow", handle_qna_workflow)
    workflow.add_node("write_answer_outline", write_answer_outline)
    workflow.add_node("process_sections", process_sections)
    workflow.add_node("generate_further_questions", generate_further_questions)

    # Define the edges
    workflow.add_edge("__start__", "reformulate_user_query")
    
    # Add conditional edges from reformulate_user_query based on research mode
    def route_after_reformulate(state: State, config) -> str:
        """Route based on research_mode after reformulating the query."""
        configuration = Configuration.from_runnable_config(config)
        
        if configuration.research_mode == ResearchMode.QNA.value:
            return "handle_qna_workflow"
        else:
            return "write_answer_outline"
    
    workflow.add_conditional_edges(
        "reformulate_user_query",
        route_after_reformulate,
        {
            "handle_qna_workflow": "handle_qna_workflow",
            "write_answer_outline": "write_answer_outline"
        }
    )
    
    # QNA workflow path: handle_qna_workflow -> generate_further_questions -> __end__
    workflow.add_edge("handle_qna_workflow", "generate_further_questions")
    
    # Report generation workflow path: write_answer_outline -> process_sections -> generate_further_questions -> __end__
    workflow.add_edge("write_answer_outline", "process_sections")
    workflow.add_edge("process_sections", "generate_further_questions")
    
    # Both paths end after generating further questions
    workflow.add_edge("generate_further_questions", "__end__")

    # Compile the workflow into an executable graph
    graph = workflow.compile()
    graph.name = "Surfsense Researcher"  # This defines the custom name in LangSmith
    
    return graph

# Compile the graph once when the module is loaded
graph = build_graph()
