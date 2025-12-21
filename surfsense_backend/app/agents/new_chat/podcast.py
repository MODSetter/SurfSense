"""
Podcast generation tool for the new chat agent.

This module provides a factory function for creating the generate_podcast tool
that integrates with the existing podcaster agent. Podcasts are saved to the
database like the old system, providing authentication and persistence.
"""

from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.podcaster.graph import graph as podcaster_graph
from app.agents.podcaster.state import State as PodcasterState
from app.db import Podcast


def create_generate_podcast_tool(
    search_space_id: int,
    db_session: AsyncSession,
    user_id: str,
):
    """
    Factory function to create the generate_podcast tool with injected dependencies.

    Args:
        search_space_id: The user's search space ID
        db_session: Database session
        user_id: The user's ID (as string)

    Returns:
        A configured tool function for generating podcasts
    """

    @tool
    async def generate_podcast(
        source_content: str,
        podcast_title: str = "SurfSense Podcast",
        user_prompt: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a podcast from the provided content.

        Use this tool when the user asks to create, generate, or make a podcast.
        Common triggers include phrases like:
        - "Give me a podcast about this"
        - "Create a podcast from this conversation"
        - "Generate a podcast summary"
        - "Make a podcast about..."
        - "Turn this into a podcast"

        The tool will generate a complete audio podcast with two speakers
        discussing the provided content in an engaging conversational format.

        Args:
            source_content: The text content to convert into a podcast.
                           This can be a summary, research findings, or any text
                           the user wants transformed into an audio podcast.
            podcast_title: Title for the podcast (default: "SurfSense Podcast")
            user_prompt: Optional instructions for podcast style, tone, or format.
                        For example: "Make it casual and fun" or "Focus on the key insights"

        Returns:
            A dictionary containing:
            - status: "success" or "error"
            - podcast_id: The database ID of the saved podcast (for API access)
            - title: The podcast title
            - transcript: Full podcast transcript with all dialogue entries
            - duration_ms: Estimated podcast duration in milliseconds
            - transcript_entries: Number of dialogue entries
        """
        try:
            # Configure the podcaster graph
            config = {
                "configurable": {
                    "podcast_title": podcast_title,
                    "user_id": str(user_id),
                    "search_space_id": search_space_id,
                    "user_prompt": user_prompt,
                }
            }

            # Initialize the podcaster state with the source content
            initial_state = PodcasterState(
                source_content=source_content,
                db_session=db_session,
            )

            # Run the podcaster graph
            result = await podcaster_graph.ainvoke(initial_state, config=config)

            # Extract results
            podcast_transcript = result.get("podcast_transcript", [])
            file_path = result.get("final_podcast_file_path", "")

            # Calculate estimated duration (rough estimate: ~150 words per minute)
            total_words = sum(
                len(entry.dialog.split()) if hasattr(entry, "dialog") else len(entry.get("dialog", "").split())
                for entry in podcast_transcript
            )
            estimated_duration_ms = int((total_words / 150) * 60 * 1000)

            # Create full transcript for display (all entries, complete dialog)
            full_transcript = []
            for entry in podcast_transcript:
                if hasattr(entry, "speaker_id"):
                    speaker = f"Speaker {entry.speaker_id + 1}"
                    dialog = entry.dialog
                else:
                    speaker = f"Speaker {entry.get('speaker_id', 0) + 1}"
                    dialog = entry.get("dialog", "")
                full_transcript.append(f"{speaker}: {dialog}")

            # Convert podcast transcript entries to serializable format (like old system)
            serializable_transcript = []
            for entry in podcast_transcript:
                if hasattr(entry, "speaker_id"):
                    serializable_transcript.append({
                        "speaker_id": entry.speaker_id,
                        "dialog": entry.dialog
                    })
                else:
                    serializable_transcript.append({
                        "speaker_id": entry.get("speaker_id", 0),
                        "dialog": entry.get("dialog", "")
                    })

            # Save podcast to database (like old system)
            # This provides authentication and persistence
            podcast = Podcast(
                title=podcast_title,
                podcast_transcript=serializable_transcript,
                file_location=file_path,
                search_space_id=search_space_id,
                # chat_id is None since new-chat uses LangGraph threads, not DB chats
                chat_id=None,
                chat_state_version=None,
            )
            db_session.add(podcast)
            await db_session.commit()
            await db_session.refresh(podcast)

            # Return podcast_id - frontend will use it to call the API endpoint
            # GET /api/v1/podcasts/{podcast_id}/stream (like the old system)
            return {
                "status": "success",
                "podcast_id": podcast.id,
                "title": podcast_title,
                "transcript": "\n\n".join(full_transcript),
                "duration_ms": estimated_duration_ms,
                "transcript_entries": len(podcast_transcript),
            }

        except Exception as e:
            error_message = str(e)
            print(f"[generate_podcast] Error: {error_message}")
            # Rollback on error
            await db_session.rollback()
            return {
                "status": "error",
                "error": error_message,
                "title": podcast_title,
                "podcast_id": None,
                "duration_ms": 0,
                "transcript_entries": 0,
            }

    return generate_podcast

