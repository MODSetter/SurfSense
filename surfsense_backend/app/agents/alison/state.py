from typing import TypedDict, List, Any

class AlisonState(TypedDict):
    """
    Represents the state of the Alison agent's workflow.
    """
    user_query: str
    identified_problem: str | None
    troubleshooting_steps: List[str] | None
    visual_aids: List[str] | None
    escalation_required: bool
    user_role: str  # "professor" or "proctor"
    final_response: str | None
    db_session: Any
    chat_history: Any
    streaming_service: Any
