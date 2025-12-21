"""
Test runner for SurfSense podcast deep agent.

This module provides a test function to verify the podcast deep agent functionality.
"""

import asyncio

from langchain_core.messages import HumanMessage

from app.agents.new_chat.llm_config import (
    create_chat_litellm_from_config,
    load_llm_config_from_yaml,
)
from app.db import async_session_maker
from app.services.connector_service import ConnectorService

from .podcast_deepagent import create_surfsense_podcast_agent

# =============================================================================
# Test Runner
# =============================================================================


async def run_test():
    """Run a basic test of the podcast deep agent."""
    print("=" * 60)
    print("Creating Podcast Deep Agent with ChatLiteLLM from global config...")
    print("=" * 60)

    # Create ChatLiteLLM from global config
    # Use global LLM config by id (negative ids are reserved for global configs)
    llm_config = load_llm_config_from_yaml(llm_config_id=-4)
    if not llm_config:
        raise ValueError("Failed to load LLM config from YAML")
    print(f"Loaded LLM config: {llm_config.get('model_name', 'unknown')}")

    llm = create_chat_litellm_from_config(llm_config)
    if not llm:
        raise ValueError("Failed to create ChatLiteLLM instance")

    # Create a real DB session + ConnectorService, then build the podcast agent.
    async with async_session_maker() as session:
        # Use a known dev search space id (adjust as needed for your environment)
        search_space_id = 2

        print(f"\nUsing search_space_id: {search_space_id}")

        connector_service = ConnectorService(session, search_space_id=search_space_id)

        agent = create_surfsense_podcast_agent(
            llm=llm,
            search_space_id=search_space_id,
            db_session=session,
            connector_service=connector_service,
            user_instructions="Create an engaging and educational podcast",
        )

        print("\nPodcast Agent created successfully!")
        print(f"Agent type: {type(agent)}")

        # Test 1: Basic invocation with sample content
        print("\n" + "=" * 60)
        print("Test 1: Generating podcast transcript from sample content...")
        print("=" * 60)

        # Sample content for podcast generation
        sample_content = """
        Artificial Intelligence (AI) is revolutionizing how we work and live. 
        Machine learning models can now understand natural language, generate images, 
        and even write code. The key breakthrough came with transformer architectures 
        in 2017, which enabled models to understand context in text much better than before.
        
        Today, AI assistants can help with everything from writing emails to debugging code.
        However, there are also concerns about AI safety, job displacement, and the 
        environmental impact of training large models.
        """

        initial_state = {
            "messages": [
                HumanMessage(
                    content=f"Generate a podcast transcript about the following content. "
                    f"Do NOT generate audio, just the transcript:\n\n{sample_content}"
                )
            ],
            "search_space_id": search_space_id,
            "chat_id": None,
            "source_content": sample_content,
        }

        print("\nInvoking podcast agent...")
        result = await agent.ainvoke(initial_state)

        print("\n" + "=" * 60)
        print("Agent Response:")
        print("=" * 60)

        # Print the response messages
        if "messages" in result:
            for msg in result["messages"]:
                msg_type = type(msg).__name__
                content = msg.content if hasattr(msg, "content") else str(msg)

                # For tool messages, show them more concisely
                if msg_type == "ToolMessage":
                    print(f"\n--- [{msg_type}] ---")
                    # Truncate long tool outputs
                    if len(content) > 500:
                        print(f"{content[:500]}...\n[truncated]")
                    else:
                        print(content)
                else:
                    print(f"\n--- [{msg_type}] ---\n{content}\n")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

    return result


async def run_search_and_podcast_test():
    """
    Run a test that searches the knowledge base first, then generates a podcast.
    
    This tests the full workflow:
    1. Search knowledge base for relevant content
    2. Generate podcast transcript from found content
    """
    print("=" * 60)
    print("Test: Search Knowledge Base → Generate Podcast")
    print("=" * 60)

    llm_config = load_llm_config_from_yaml(llm_config_id=-1)
    if not llm_config:
        raise ValueError("Failed to load LLM config from YAML")

    llm = create_chat_litellm_from_config(llm_config)
    if not llm:
        raise ValueError("Failed to create ChatLiteLLM instance")

    async with async_session_maker() as session:
        search_space_id = 5

        connector_service = ConnectorService(session, search_space_id=search_space_id)

        agent = create_surfsense_podcast_agent(
            llm=llm,
            search_space_id=search_space_id,
            db_session=session,
            connector_service=connector_service,
        )

        initial_state = {
            "messages": [
                HumanMessage(
                    content="Search my knowledge base for information about AI or machine learning, "
                    "then generate a podcast transcript about what you find. "
                    "Do NOT generate audio yet."
                )
            ],
            "search_space_id": search_space_id,
            "chat_id": None,
            "source_content": None,
        }

        print("\nInvoking agent with search + transcript generation...")
        result = await agent.ainvoke(initial_state)

        print("\n" + "=" * 60)
        print("Agent Response:")
        print("=" * 60)

        if "messages" in result:
            for msg in result["messages"]:
                msg_type = type(msg).__name__
                content = msg.content if hasattr(msg, "content") else str(msg)

                if msg_type == "ToolMessage":
                    print(f"\n--- [{msg_type}] ---")
                    if len(content) > 500:
                        print(f"{content[:500]}...\n[truncated]")
                    else:
                        print(content)
                else:
                    print(f"\n--- [{msg_type}] ---\n{content}\n")

    return result


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  SURFSENSE PODCAST DEEP AGENT TEST")
    print("=" * 70 + "\n")

    # Run the basic test
    asyncio.run(run_test())

    # Uncomment to run the search + podcast test:
    # print("\n\n")
    # asyncio.run(run_search_and_podcast_test())

