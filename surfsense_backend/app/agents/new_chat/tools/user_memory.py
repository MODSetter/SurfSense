"""
User memory tools for the SurfSense agent.

This module provides tools for storing and retrieving user memories,
enabling personalized AI responses similar to Claude's memory feature.

Features:
- save_memory: Store facts, preferences, and context about the user
- recall_memory: Retrieve relevant memories using semantic search
"""

import logging
from typing import Any
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import MemoryCategory, UserMemory

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Default number of memories to retrieve
DEFAULT_RECALL_TOP_K = 5

# Maximum number of memories per user (to prevent unbounded growth)
MAX_MEMORIES_PER_USER = 100


# =============================================================================
# Helper Functions
# =============================================================================


def _to_uuid(user_id: str) -> UUID:
    """Convert a string user_id to a UUID object."""
    if isinstance(user_id, UUID):
        return user_id
    return UUID(user_id)


async def get_user_memory_count(
    db_session: AsyncSession,
    user_id: str,
    search_space_id: int | None = None,
) -> int:
    """Get the count of memories for a user."""
    uuid_user_id = _to_uuid(user_id)
    query = select(UserMemory).where(UserMemory.user_id == uuid_user_id)
    if search_space_id is not None:
        query = query.where(
            (UserMemory.search_space_id == search_space_id)
            | (UserMemory.search_space_id.is_(None))
        )
    result = await db_session.execute(query)
    return len(result.scalars().all())


async def delete_oldest_memory(
    db_session: AsyncSession,
    user_id: str,
    search_space_id: int | None = None,
) -> None:
    """Delete the oldest memory for a user to make room for new ones."""
    uuid_user_id = _to_uuid(user_id)
    query = (
        select(UserMemory)
        .where(UserMemory.user_id == uuid_user_id)
        .order_by(UserMemory.updated_at.asc())
        .limit(1)
    )
    if search_space_id is not None:
        query = query.where(
            (UserMemory.search_space_id == search_space_id)
            | (UserMemory.search_space_id.is_(None))
        )
    result = await db_session.execute(query)
    oldest_memory = result.scalars().first()
    if oldest_memory:
        await db_session.delete(oldest_memory)
        await db_session.commit()


def format_memories_for_context(memories: list[dict[str, Any]]) -> str:
    """Format retrieved memories into a readable context string for the LLM."""
    if not memories:
        return "No relevant memories found for this user."

    parts = ["<user_memories>"]
    for memory in memories:
        category = memory.get("category", "unknown")
        text = memory.get("memory_text", "")
        updated = memory.get("updated_at", "")
        parts.append(
            f"  <memory category='{category}' updated='{updated}'>{text}</memory>"
        )
    parts.append("</user_memories>")

    return "\n".join(parts)


# =============================================================================
# Tool Factory Functions
# =============================================================================


def create_save_memory_tool(
    user_id: str,
    search_space_id: int,
    db_session: AsyncSession,
):
    """
    Factory function to create the save_memory tool.

    Args:
        user_id: The user's UUID
        search_space_id: The search space ID (for space-specific memories)
        db_session: Database session for executing queries

    Returns:
        A configured tool function for saving user memories
    """

    @tool
    async def save_memory(
        content: str,
        category: str = "fact",
    ) -> dict[str, Any]:
        """
        Save a fact, preference, or context about the user for future reference.

        Use this tool when:
        - User explicitly says "remember this", "keep this in mind", or similar
        - User shares personal preferences (e.g., "I prefer Python over JavaScript")
        - User shares important facts about themselves (name, role, interests, projects)
        - User gives standing instructions (e.g., "always respond in bullet points")
        - User shares relevant context (e.g., "I'm working on project X")

        The saved information will be available in future conversations to provide
        more personalized and contextual responses.

        Args:
            content: The fact/preference/context to remember.
                    Phrase it clearly, e.g., "User prefers dark mode",
                    "User is a senior Python developer", "User is working on an AI project"
            category: Type of memory. One of:
                    - "preference": User preferences (e.g., coding style, tools, formats)
                    - "fact": Facts about the user (e.g., name, role, expertise)
                    - "instruction": Standing instructions (e.g., response format preferences)
                    - "context": Current context (e.g., ongoing projects, goals)

        Returns:
            A dictionary with the save status and memory details
        """
        # Normalize and validate category (LLMs may send uppercase)
        category = category.lower() if category else "fact"
        valid_categories = ["preference", "fact", "instruction", "context"]
        if category not in valid_categories:
            category = "fact"

        try:
            # Convert user_id to UUID
            uuid_user_id = _to_uuid(user_id)

            # Check if we've hit the memory limit
            memory_count = await get_user_memory_count(
                db_session, user_id, search_space_id
            )
            if memory_count >= MAX_MEMORIES_PER_USER:
                # Delete oldest memory to make room
                await delete_oldest_memory(db_session, user_id, search_space_id)

            # Generate embedding for the memory
            embedding = config.embedding_model_instance.embed(content)

            # Create new memory using ORM
            # The pgvector Vector column type handles embedding conversion automatically
            new_memory = UserMemory(
                user_id=uuid_user_id,
                search_space_id=search_space_id,
                memory_text=content,
                category=MemoryCategory(category),  # Convert string to enum
                embedding=embedding,  # Pass embedding directly (list or numpy array)
            )

            db_session.add(new_memory)
            await db_session.commit()
            await db_session.refresh(new_memory)

            return {
                "status": "saved",
                "memory_id": new_memory.id,
                "memory_text": content,
                "category": category,
                "message": f"I'll remember: {content}",
            }

        except Exception as e:
            logger.exception(f"Failed to save memory for user {user_id}: {e}")
            # Rollback the session to clear any failed transaction state
            await db_session.rollback()
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to save memory. Please try again.",
            }

    return save_memory


def create_recall_memory_tool(
    user_id: str,
    search_space_id: int,
    db_session: AsyncSession,
):
    """
    Factory function to create the recall_memory tool.

    Args:
        user_id: The user's UUID
        search_space_id: The search space ID
        db_session: Database session for executing queries

    Returns:
        A configured tool function for recalling user memories
    """

    @tool
    async def recall_memory(
        query: str | None = None,
        category: str | None = None,
        top_k: int = DEFAULT_RECALL_TOP_K,
    ) -> dict[str, Any]:
        """
        Recall relevant memories about the user to provide personalized responses.

        Use this tool when:
        - You need user context to give a better, more personalized answer
        - User asks about their preferences or past information they shared
        - User references something they told you before
        - Personalization would significantly improve the response quality
        - User asks "what do you know about me?" or similar

        Args:
            query: Optional search query to find specific memories.
                  If not provided, returns the most recent memories.
                  Example: "programming preferences", "current projects"
            category: Optional category filter. One of:
                     "preference", "fact", "instruction", "context"
                     If not provided, searches all categories.
            top_k: Number of memories to retrieve (default: 5, max: 20)

        Returns:
            A dictionary containing relevant memories and formatted context
        """
        top_k = min(max(top_k, 1), 20)  # Clamp between 1 and 20

        try:
            # Convert user_id to UUID
            uuid_user_id = _to_uuid(user_id)

            if query:
                # Semantic search using embeddings
                query_embedding = config.embedding_model_instance.embed(query)

                # Build query with vector similarity
                stmt = (
                    select(UserMemory)
                    .where(UserMemory.user_id == uuid_user_id)
                    .where(
                        (UserMemory.search_space_id == search_space_id)
                        | (UserMemory.search_space_id.is_(None))
                    )
                )

                # Add category filter if specified
                if category and category in [
                    "preference",
                    "fact",
                    "instruction",
                    "context",
                ]:
                    stmt = stmt.where(UserMemory.category == MemoryCategory(category))

                # Order by vector similarity
                stmt = stmt.order_by(
                    UserMemory.embedding.op("<=>")(query_embedding)
                ).limit(top_k)

            else:
                # No query - return most recent memories
                stmt = (
                    select(UserMemory)
                    .where(UserMemory.user_id == uuid_user_id)
                    .where(
                        (UserMemory.search_space_id == search_space_id)
                        | (UserMemory.search_space_id.is_(None))
                    )
                )

                # Add category filter if specified
                if category and category in [
                    "preference",
                    "fact",
                    "instruction",
                    "context",
                ]:
                    stmt = stmt.where(UserMemory.category == MemoryCategory(category))

                stmt = stmt.order_by(UserMemory.updated_at.desc()).limit(top_k)

            result = await db_session.execute(stmt)
            memories = result.scalars().all()

            # Format memories for response
            memory_list = [
                {
                    "id": m.id,
                    "memory_text": m.memory_text,
                    "category": m.category.value if m.category else "unknown",
                    "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                }
                for m in memories
            ]

            formatted_context = format_memories_for_context(memory_list)

            return {
                "status": "success",
                "count": len(memory_list),
                "memories": memory_list,
                "formatted_context": formatted_context,
            }

        except Exception as e:
            logger.exception(f"Failed to recall memories for user {user_id}: {e}")
            await db_session.rollback()
            return {
                "status": "error",
                "error": str(e),
                "memories": [],
                "formatted_context": "Failed to recall memories.",
            }

    return recall_memory
