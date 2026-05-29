"""Run one ``agent_task`` invocation: ainvoke + auto-decision resume loop."""

from __future__ import annotations

import time
import uuid
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.agents.multi_agent_chat import create_multi_agent_chat_deep_agent
from app.db import ChatVisibility, async_session_maker

from ..types import ActionContext
from .auto_decide import build_auto_decisions
from .dependencies import build_dependencies
from .finalize import extract_final_assistant_message

# Cap on HITL resume iterations. The agent should not need this many turns in one
# step; treat overshoot as a runaway and fail the step.
_MAX_RESUMES = 50


async def run_agent_task(
    *,
    ctx: ActionContext,
    query: str,
    auto_approve_all: bool,
) -> dict[str, Any]:
    """Invoke multi_agent_chat for one rendered query and return its outcome.

    Opens its own DB session so the executor's bookkeeping session isn't tied
    up for the entire invocation. The LangGraph ``thread_id`` (a fresh UUID)
    is returned as ``agent_session_id`` for later inspection.
    """
    agent_session_id = str(uuid.uuid4())
    user_id = str(ctx.creator_user_id) if ctx.creator_user_id else None
    decision = "approve" if auto_approve_all else "reject"

    async with async_session_maker() as agent_session:
        deps = await build_dependencies(
            session=agent_session,
            search_space_id=ctx.search_space_id,
        )

        agent = await create_multi_agent_chat_deep_agent(
            llm=deps.llm,
            search_space_id=ctx.search_space_id,
            db_session=agent_session,
            connector_service=deps.connector_service,
            checkpointer=deps.checkpointer,
            user_id=user_id,
            thread_id=None,
            agent_config=deps.agent_config,
            firecrawl_api_key=deps.firecrawl_api_key,
            thread_visibility=ChatVisibility.PRIVATE,
        )

        request_id = f"automation:{ctx.run_id}:{ctx.step_id}"
        turn_id = f"{request_id}:{int(time.time() * 1000)}"
        input_state: dict[str, Any] = {
            "messages": [HumanMessage(content=query)],
            "search_space_id": ctx.search_space_id,
            "request_id": request_id,
            "turn_id": turn_id,
        }
        config: dict[str, Any] = {
            "configurable": {
                "thread_id": agent_session_id,
                "request_id": request_id,
                "turn_id": turn_id,
            },
            "recursion_limit": 10_000,
        }

        result = await agent.ainvoke(input_state, config=config)

        resumes = 0
        while True:
            state = await agent.aget_state(config)
            if not getattr(state, "interrupts", None):
                break
            if resumes >= _MAX_RESUMES:
                raise RuntimeError(
                    f"agent_task exceeded {_MAX_RESUMES} HITL resume iterations"
                )
            lg_resume_map, routed = build_auto_decisions(state, decision)
            config["configurable"]["surfsense_resume_value"] = routed
            result = await agent.ainvoke(Command(resume=lg_resume_map), config=config)
            resumes += 1

    return {
        "agent_session_id": agent_session_id,
        "final_message": extract_final_assistant_message(result),
        "resumes": resumes,
    }
