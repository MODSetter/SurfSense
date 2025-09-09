import json
from typing import Any, List

from langchain_core.runnables import RunnableConfig
from langgraph.types import StreamWriter

from .state import AlisonState
from .prompts import (
    get_alison_system_prompt,
    get_problem_identification_prompt,
    get_escalation_prompt,
)

from langchain_core.messages import SystemMessage, HumanMessage
from app.services.llm_service import get_user_fast_llm


async def identify_problem(state: AlisonState, config: RunnableConfig, writer: StreamWriter) -> dict[str, Any]:
    """
    Identifies the user's problem based on their query.
    """
    user_id = config["configurable"]["user_id"]
    user_query = state["user_query"]

    llm = await get_user_fast_llm(state["db_session"], user_id)
    if not llm:
        # Handle case where LLM is not configured
        # For now, we'll just return a default problem
        return {"identified_problem": "Could not identify problem: LLM not configured."}

    prompt = get_problem_identification_prompt().format(user_query=user_query)
    messages = [
        SystemMessage(content=get_alison_system_prompt()),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    identified_problem = response.content.strip()

    return {"identified_problem": identified_problem}

from app.retriever.alison_knowledge_retriever import AlisonKnowledgeRetriever

async def search_knowledge_base(state: AlisonState, config: RunnableConfig, writer: StreamWriter) -> dict[str, Any]:
    """
    Searches the knowledge base for troubleshooting guides related to the identified problem.
    """
    identified_problem = state["identified_problem"]
    if not identified_problem:
        return {"troubleshooting_steps": [], "visual_aids": []}

    retriever = AlisonKnowledgeRetriever(state["db_session"])
    documents = await retriever.hybrid_search(identified_problem, top_k=3)

    if not documents:
        return {"troubleshooting_steps": [], "visual_aids": []}

    # For now, we'll just return the content of the first document.
    # We can improve this later to synthesize an answer from multiple documents.
    first_document_content = documents[0]["content"]

    return {"troubleshooting_steps": [first_document_content], "visual_aids": []}

async def generate_troubleshooting_response(state: AlisonState, config: RunnableConfig, writer: StreamWriter) -> dict[str, Any]:
    """
    Generates a response with troubleshooting steps and visual aids.
    """
    troubleshooting_steps = state.get("troubleshooting_steps")
    if not troubleshooting_steps:
        return {"escalation_required": True}

    user_role = config["configurable"].get("user_role", "professor")
    content = troubleshooting_steps[0]  # Assuming only one document is returned for now

    # Simple markdown parsing
    sections = {}
    current_section = None
    for line in content.split('\\n'):
        if line.startswith("## "):
            current_section = line[3:].strip()
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(line)

    response_parts = []
    if "Issue" in sections:
        response_parts.append(f"I understand you're having an issue with: **{''.join(sections['Issue'])}**")
        response_parts.append("Here are some steps you can try:")

    if "Troubleshooting Steps" in sections:
        response_parts.extend(sections["Troubleshooting Steps"])

    if "Role-Specific Advice" in sections:
        advice_text = '\\n'.join(sections['Role-Specific Advice'])
        if f"- **{user_role.capitalize()}:**" in advice_text:
            role_advice = [line for line in advice_text.split('\\n') if line.startswith(f"- **{user_role.capitalize()}:**")]
            if role_advice:
                response_parts.append("\\n**Advice for you as a {user_role}:**")
                response_parts.append(role_advice[0].replace(f"- **{user_role.capitalize()}:**", "").strip())

    if "Visual Aid" in sections:
        for line in sections["Visual Aid"]:
            if "[Image:" in line:
                response_parts.append(f"You can also refer to this visual guide: {line}")

    final_response = "\\n".join(response_parts)
    return {"final_response": final_response}

async def handle_escalation(state: AlisonState, config: RunnableConfig, writer: StreamWriter) -> dict[str, Any]:
    """
    Generates a response for escalating the issue to IT support.
    """
    user_id = config["configurable"]["user_id"]
    identified_problem = state["identified_problem"]

    llm = await get_user_fast_llm(state["db_session"], user_id)
    if not llm:
        return {"final_response": "I am unable to resolve this issue. Please contact IT support."}

    prompt = get_escalation_prompt().format(identified_problem=identified_problem)
    messages = [
        SystemMessage(content=get_alison_system_prompt()),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    escalation_message = response.content.strip()

    return {"final_response": escalation_message}
