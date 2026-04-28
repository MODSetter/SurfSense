"""Calendar-focused subagent implementation."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain.agents import create_agent

from app.agents.multi_agent_v1.contracts import SubagentTaskPlan
from app.agents.multi_agent_v1.subagents.utils import (
    build_disabled_tools_list,
    build_subagent_error_result,
    build_subagent_input_state,
    build_subagent_run_config,
    extract_final_ai_message_text_from_state,
    load_llm_for_request,
    read_optional_integer,
    read_optional_nonempty_string,
)
from app.agents.new_chat.system_prompt import build_surfsense_system_prompt
from app.agents.new_chat.tools.registry import (
    build_tools_async,
    get_connector_gated_tools,
)
from app.db import ChatVisibility, async_session_maker
from app.services.connector_service import ConnectorService

CALENDAR_SUBAGENT_READ_ONLY_TOOLS: tuple[str, ...] = (
    "get_connected_accounts",
    "search_calendar_events",
    "search_surfsense_docs",
    "web_search",
)


class CalendarSubagent:
    async def run(
        self,
        *,
        plan: SubagentTaskPlan,
        stream_kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        search_space_id = stream_kwargs.get("search_space_id")
        if not isinstance(search_space_id, int):
            return build_subagent_error_result("invalid_search_space_id")

        llm_config_id = stream_kwargs.get("llm_config_id")
        if not isinstance(llm_config_id, int):
            return build_subagent_error_result("invalid_llm_config_id")

        async with async_session_maker() as session:
            llm = await load_llm_for_request(
                session=session,
                llm_config_id=llm_config_id,
                search_space_id=search_space_id,
            )
            if llm is None:
                return build_subagent_error_result("missing_llm")

            agent = await _create_calendar_subagent_agent(
                session=session,
                llm=llm,
                search_space_id=search_space_id,
                disabled_tools=build_disabled_tools_list(
                    stream_kwargs.get("disabled_tools")
                ),
                user_id=read_optional_nonempty_string(stream_kwargs, "user_id"),
                thread_id=read_optional_integer(stream_kwargs, "chat_id"),
                thread_visibility=stream_kwargs.get("thread_visibility")
                or ChatVisibility.PRIVATE,
            )
            state = await agent.ainvoke(
                build_subagent_input_state(goal=plan.goal, stream_kwargs=stream_kwargs),
                config=build_subagent_run_config(
                    stream_kwargs=stream_kwargs,
                    scope="calendar",
                ),
            )
            summary = extract_final_ai_message_text_from_state(state)
            if not summary:
                return build_subagent_error_result("empty_subagent_summary")
            return {
                "status": "success",
                "summary": summary,
                "evidence": [],
                "artifacts": [],
                "needs_human": False,
                "error_class": None,
            }


async def _create_calendar_subagent_agent(
    *,
    session: Any,
    llm: Any,
    search_space_id: int,
    disabled_tools: list[str],
    user_id: str | None,
    thread_id: int | None,
    thread_visibility: ChatVisibility,
) -> Any:
    connector_service = ConnectorService(session, search_space_id=search_space_id)
    available_connector_enums = await connector_service.get_available_connectors(
        search_space_id
    )
    available_connectors = [
        connector.value if hasattr(connector, "value") else str(connector)
        for connector in available_connector_enums
    ]
    available_document_types = await connector_service.get_available_document_types(
        search_space_id
    )
    effective_disabled_tools = list(disabled_tools)
    effective_disabled_tools.extend(get_connector_gated_tools(available_connectors))
    dependencies = {
        "search_space_id": search_space_id,
        "db_session": session,
        "connector_service": connector_service,
        "user_id": user_id,
        "thread_id": thread_id,
        "thread_visibility": thread_visibility,
        "available_connectors": available_connectors,
        "available_document_types": available_document_types,
        "llm": llm,
    }
    tools = await build_tools_async(
        dependencies=dependencies,
        enabled_tools=list(CALENDAR_SUBAGENT_READ_ONLY_TOOLS),
        disabled_tools=effective_disabled_tools,
    )
    system_prompt = build_surfsense_system_prompt(
        thread_visibility=thread_visibility,
        enabled_tool_names={tool.name for tool in tools},
        disabled_tool_names=set(effective_disabled_tools),
    )
    return await asyncio.to_thread(
        create_agent,
        llm,
        system_prompt=system_prompt,
        tools=tools,
    )
