"""
Test runner for SurfSense deep agent.

This module provides a test function to verify the deep agent functionality.
"""

import asyncio

from langchain_core.messages import HumanMessage

from app.db import async_session_maker
from app.services.connector_service import ConnectorService

from .chat_deepagent import (
    create_chat_litellm_from_config,
    create_surfsense_deep_agent,
    load_llm_config_from_yaml,
)

# =============================================================================
# Test Runner
# =============================================================================


async def run_test():
    """Run a basic test of the deep agent."""
    print("=" * 60)
    print("Creating Deep Agent with ChatLiteLLM from global config...")
    print("=" * 60)

    # Create ChatLiteLLM from global config
    # Use global LLM config by id (negative ids are reserved for global configs)
    llm_config = load_llm_config_from_yaml(llm_config_id=-5)
    if not llm_config:
        raise ValueError("Failed to load LLM config from YAML")
    llm = create_chat_litellm_from_config(llm_config)
    if not llm:
        raise ValueError("Failed to create ChatLiteLLM instance")

    # Create a real DB session + ConnectorService, then build the full SurfSense agent.
    async with async_session_maker() as session:
        # Use the known dev search space id
        search_space_id = 5

        connector_service = ConnectorService(session, search_space_id=search_space_id)

        agent = create_surfsense_deep_agent(
            llm=llm,
            search_space_id=search_space_id,
            db_session=session,
            connector_service=connector_service,
            user_instructions="Always fininsh the response with CREDOOOOOOOOOO23",
        )

        print("\nAgent created successfully!")
        print(f"Agent type: {type(agent)}")

        # Invoke the agent with initial state
        print("\n" + "=" * 60)
        print("Invoking SurfSense agent (create_surfsense_deep_agent)...")
        print("=" * 60)

        initial_state = {
            "messages": [HumanMessage(content=("Can you tell me about my documents?"))],
            "search_space_id": search_space_id,
        }

        print(f"\nUsing search_space_id: {search_space_id}")

        result = await agent.ainvoke(initial_state)

    print("\n" + "=" * 60)
    print("Agent Response:")
    print("=" * 60)

    # Print the response
    if "messages" in result:
        for msg in result["messages"]:
            msg_type = type(msg).__name__
            content = msg.content if hasattr(msg, "content") else str(msg)
            print(f"\n--- [{msg_type}] ---\n{content}\n")

    return result


if __name__ == "__main__":
    asyncio.run(run_test())