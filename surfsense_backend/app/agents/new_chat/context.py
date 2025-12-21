"""
Context schema definitions for SurfSense agents.

This module defines the custom state schema used by the SurfSense deep agent.
"""

from typing import TypedDict


class SurfSenseContextSchema(TypedDict):
    """
    Custom state schema for the SurfSense deep agent.

    This extends the default agent state with custom fields.
    The default state already includes:
    - messages: Conversation history
    - todos: Task list from TodoListMiddleware
    - files: Virtual filesystem from FilesystemMiddleware

    We're adding fields needed for knowledge base search:
    - search_space_id: The user's search space ID
    - db_session: Database session (injected at runtime)
    - connector_service: Connector service instance (injected at runtime)
    """

    search_space_id: int
    # These are runtime-injected and won't be serialized
    # db_session and connector_service are passed when invoking the agent
