from langgraph.graph import StateGraph, END
from .state import AlisonState
from .nodes import (
    identify_problem,
    search_knowledge_base,
    generate_troubleshooting_response,
    handle_escalation,
)

def build_graph():
    """
    Builds the LangGraph workflow for the Alison agent.
    """
    workflow = StateGraph(AlisonState)

    workflow.add_node("identify_problem", identify_problem)
    workflow.add_node("search_knowledge_base", search_knowledge_base)
    workflow.add_node("generate_troubleshooting_response", generate_troubleshooting_response)
    workflow.add_node("handle_escalation", handle_escalation)

    workflow.set_entry_point("identify_problem")

    workflow.add_edge("identify_problem", "search_knowledge_base")
    workflow.add_edge("search_knowledge_base", "generate_troubleshooting_response")

    def should_escalate(state: AlisonState) -> str:
        """
        Determines whether to escalate to IT support or end the conversation.
        """
        if state.get("escalation_required"):
            return "handle_escalation"
        return END

    workflow.add_conditional_edges(
        "generate_troubleshooting_response",
        should_escalate,
        {
            "handle_escalation": "handle_escalation",
            END: END,
        },
    )

    workflow.add_edge("handle_escalation", END)

    graph = workflow.compile()
    graph.name = "Alison IT Support Assistant"
    return graph

graph = build_graph()
