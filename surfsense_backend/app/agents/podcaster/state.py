"""Define the state structures for the agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

class PodcastTranscriptEntry(BaseModel):
    """
    Represents a single entry in a podcast transcript.
    """
    speaker_id: int = Field(..., description="The ID of the speaker (0 or 1)")
    dialog: str = Field(..., description="The dialog text spoken by the speaker")


class PodcastTranscripts(BaseModel):
    """
    Represents the full podcast transcript structure.
    """
    podcast_transcripts: List[PodcastTranscriptEntry] = Field(
        ..., 
        description="List of transcript entries with alternating speakers"
    ) 

@dataclass
class State:
    """Defines the input state for the agent, representing a narrower interface to the outside world.

    This class is used to define the initial state and structure of incoming data.
    See: https://langchain-ai.github.io/langgraph/concepts/low_level/#state
    for more information.
    """
    # Runtime context
    db_session: AsyncSession
    source_content: str
    podcast_transcript: Optional[List[PodcastTranscriptEntry]] = None
    final_podcast_file_path: Optional[str] = None
