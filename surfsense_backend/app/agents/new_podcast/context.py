"""
Context schema definitions for SurfSense podcast agent.

This module defines the custom state schema used by the SurfSense podcast deep agent.
"""

from typing import TypedDict


class PodcastContextSchema(TypedDict):
    """
    Custom state schema for the SurfSense podcast deep agent.

    This extends the default agent state with custom fields.
    The default state already includes:
    - messages: Conversation history
    - todos: Task list from TodoListMiddleware
    - files: Virtual filesystem from FilesystemMiddleware

    We're adding fields needed for podcast generation:
    - search_space_id: The user's search space ID
    - chat_id: Optional chat ID if generating podcast from a chat
    - source_content: Optional pre-provided content for podcast generation
    """

    search_space_id: int
    chat_id: int | None
    source_content: str | None
    # These are runtime-injected and won't be serialized
    # db_session and connector_service are passed when invoking the agent

