"""
Podcast generation tools for the podcast deep agent.

This module provides:
- Tool factory for generating podcast transcripts
- Tool factory for generating podcast audio from transcripts
"""

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any

from ffmpeg.asyncio import FFmpeg
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from litellm import aspeech
from pydantic import BaseModel, Field

from app.agents.podcaster.prompts import get_podcast_generation_prompt
from app.agents.podcaster.utils import get_voice_for_provider
from app.config import config as app_config
from app.services.kokoro_tts_service import get_kokoro_tts_service

# =============================================================================
# Pydantic Models for Podcast Transcript
# =============================================================================


class PodcastTranscriptEntry(BaseModel):
    """A single entry in the podcast transcript."""

    speaker_id: int = Field(..., description="The ID of the speaker (0 or 1)")
    dialog: str = Field(..., description="The dialog text spoken by the speaker")


class PodcastTranscripts(BaseModel):
    """The full podcast transcript structure."""

    podcast_transcripts: list[PodcastTranscriptEntry] = Field(
        ..., description="List of transcript entries with alternating speakers"
    )


# =============================================================================
# Podcast Transcript Generation Tool
# =============================================================================


def create_generate_podcast_transcript_tool(
    llm: BaseChatModel,
):
    """
    Factory function to create the generate_podcast_transcript tool with injected LLM.

    Args:
        llm: The language model to use for generating podcast transcripts.
             This should be the same LLM used by the agent.

    Returns:
        A configured tool function
    """

    @tool
    async def generate_podcast_transcript(
        source_content: str,
        user_prompt: str | None = None,
    ) -> str:
        """
        Generate a podcast transcript from source content.

        This creates a natural conversation between two podcast hosts (Speaker 0 and Speaker 1)
        based on the provided content. The transcript follows a structured format suitable for
        text-to-speech conversion.

        Args:
            source_content: The content to turn into a podcast conversation. This can be:
                           - A document or article text
                           - Chat history
                           - Research notes
                           - Any text content the user wants to discuss
            user_prompt: Optional instructions for the podcast style/focus.
                        Examples: "make it funny", "focus on technical details",
                        "keep it under 3 minutes", "make it educational for beginners"

        Returns:
            JSON string containing:
            - success: boolean indicating if generation succeeded
            - podcast_transcripts: array of {speaker_id, dialog} entries
            - error: error message if generation failed
        """
        # Get the prompt using the existing podcast prompts
        prompt = get_podcast_generation_prompt(user_prompt)

        # Create the messages for the LLM
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=f"<source_content>{source_content}</source_content>"),
        ]

        try:
            # Generate the podcast transcript
            llm_response = await llm.ainvoke(messages)

            # Try direct JSON parsing first
            try:
                podcast_transcript = PodcastTranscripts.model_validate(
                    json.loads(llm_response.content)
                )
                return json.dumps({
                    "success": True,
                    "podcast_transcripts": [
                        {"speaker_id": e.speaker_id, "dialog": e.dialog}
                        for e in podcast_transcript.podcast_transcripts
                    ],
                })
            except (json.JSONDecodeError, ValueError) as parse_error:
                print(f"Direct JSON parsing failed, trying fallback: {parse_error!s}")

                # Fallback: Extract JSON from response content
                content = llm_response.content
                json_start = content.find("{")
                json_end = content.rfind("}") + 1

                if json_start >= 0 and json_end > json_start:
                    json_str = content[json_start:json_end]
                    parsed_data = json.loads(json_str)
                    podcast_transcript = PodcastTranscripts.model_validate(parsed_data)

                    return json.dumps({
                        "success": True,
                        "podcast_transcripts": [
                            {"speaker_id": e.speaker_id, "dialog": e.dialog}
                            for e in podcast_transcript.podcast_transcripts
                        ],
                    })
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Could not find valid JSON in LLM response: {content[:200]}...",
                    })

        except Exception as e:
            print(f"Error generating podcast transcript: {e!s}")
            return json.dumps({
                "success": False,
                "error": f"Failed to generate transcript: {e!s}",
            })

    return generate_podcast_transcript


# =============================================================================
# Podcast Audio Generation Tool
# =============================================================================


def create_generate_podcast_audio_tool():
    """
    Factory function to create the generate_podcast_audio tool.

    Returns:
        A configured tool function
    """

    @tool
    async def generate_podcast_audio(
        transcript_json: str,
    ) -> str:
        """
        Generate audio for a podcast transcript and merge into a single MP3 file.

        This tool takes a podcast transcript (from generate_podcast_transcript) and:
        1. Generates speech audio for each dialog entry using TTS
        2. Merges all audio segments into a single podcast MP3 file
        3. Cleans up temporary audio files

        Args:
            transcript_json: JSON string containing the podcast_transcripts array.
                           Expected format:
                           {
                             "podcast_transcripts": [
                               {"speaker_id": 0, "dialog": "Hello..."},
                               {"speaker_id": 1, "dialog": "Hi there..."}
                             ]
                           }
                           OR the direct output from generate_podcast_transcript

        Returns:
            JSON string containing:
            - success: boolean indicating if generation succeeded
            - file_path: path to the generated podcast MP3 file
            - segments_count: number of audio segments in the podcast
            - error: error message if generation failed
        """
        # Parse the transcript JSON
        try:
            data = json.loads(transcript_json)
            # Handle both direct transcript format and wrapped format
            if "podcast_transcripts" in data:
                transcript_entries = data["podcast_transcripts"]
            elif isinstance(data, list):
                transcript_entries = data
            else:
                return json.dumps({
                    "success": False,
                    "error": "Invalid transcript format: expected 'podcast_transcripts' array or direct array",
                })
        except json.JSONDecodeError as e:
            return json.dumps({
                "success": False,
                "error": f"Invalid JSON input: {e!s}",
            })

        if not transcript_entries:
            return json.dumps({
                "success": False,
                "error": "No transcript entries provided",
            })

        # Add intro segment
        starting_transcript = {"speaker_id": 1, "dialog": "Welcome to Surfsense Podcast."}
        merged_transcript = [starting_transcript, *transcript_entries]

        # Create temporary directory for audio files
        temp_dir = Path("temp_audio")
        temp_dir.mkdir(exist_ok=True)

        # Generate unique session ID for this podcast
        session_id = str(uuid.uuid4())
        output_path = f"podcasts/{session_id}_podcast.mp3"
        os.makedirs("podcasts", exist_ok=True)

        audio_files: list[str] = []

        async def generate_speech_for_segment(
            segment: dict[str, Any], index: int
        ) -> str:
            """Generate speech audio for a single transcript segment."""
            speaker_id = segment.get("speaker_id", 0)
            dialog = segment.get("dialog", "")

            if not dialog.strip():
                raise ValueError(f"Empty dialog for segment {index}")

            # Get voice based on speaker and TTS provider
            voice = get_voice_for_provider(app_config.TTS_SERVICE, speaker_id)

            if app_config.TTS_SERVICE == "local/kokoro":
                # Kokoro generates WAV files
                filename = f"{temp_dir}/{session_id}_{index}.wav"
                kokoro_service = await get_kokoro_tts_service(lang_code="a")
                audio_path = await kokoro_service.generate_speech(
                    text=dialog, voice=voice, speed=1.0, output_path=filename
                )
                return audio_path
            else:
                # Other TTS services generate MP3 files
                filename = f"{temp_dir}/{session_id}_{index}.mp3"

                if app_config.TTS_SERVICE_API_BASE:
                    response = await aspeech(
                        model=app_config.TTS_SERVICE,
                        api_base=app_config.TTS_SERVICE_API_BASE,
                        api_key=app_config.TTS_SERVICE_API_KEY,
                        voice=voice,
                        input=dialog,
                        max_retries=2,
                        timeout=600,
                    )
                else:
                    response = await aspeech(
                        model=app_config.TTS_SERVICE,
                        api_key=app_config.TTS_SERVICE_API_KEY,
                        voice=voice,
                        input=dialog,
                        max_retries=2,
                        timeout=600,
                    )

                with open(filename, "wb") as f:
                    f.write(response.content)

                return filename

        try:
            # Generate all audio files concurrently
            tasks = [
                generate_speech_for_segment(segment, i)
                for i, segment in enumerate(merged_transcript)
            ]
            audio_files = await asyncio.gather(*tasks)

            # Merge audio files using FFmpeg
            ffmpeg = FFmpeg().option("y")

            # Add each audio file as input
            for audio_file in audio_files:
                ffmpeg = ffmpeg.input(audio_file)

            # Configure the concatenation filter
            filter_complex_parts = []
            for i in range(len(audio_files)):
                filter_complex_parts.append(f"[{i}:0]")

            filter_complex_str = (
                "".join(filter_complex_parts)
                + f"concat=n={len(audio_files)}:v=0:a=1[outa]"
            )
            ffmpeg = ffmpeg.option("filter_complex", filter_complex_str)
            ffmpeg = ffmpeg.output(output_path, map="[outa]")

            # Execute FFmpeg
            await ffmpeg.execute()

            print(f"Successfully created podcast audio: {output_path}")

            return json.dumps({
                "success": True,
                "file_path": output_path,
                "segments_count": len(merged_transcript),
            })

        except Exception as e:
            print(f"Error generating podcast audio: {e!s}")
            return json.dumps({
                "success": False,
                "error": f"Failed to generate podcast audio: {e!s}",
            })
        finally:
            # Clean up temporary audio files
            for audio_file in audio_files:
                try:
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
                except Exception as cleanup_error:
                    print(f"Error removing temp file {audio_file}: {cleanup_error!s}")

    return generate_podcast_audio

