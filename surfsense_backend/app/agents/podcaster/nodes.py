import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any

from ffmpeg.asyncio import FFmpeg
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from litellm import aspeech

from app.config import config as app_config
from app.services.kokoro_tts_service import get_kokoro_tts_service
from app.services.llm_service import get_user_long_context_llm

from .configuration import Configuration
from .prompts import get_podcast_generation_prompt
from .state import PodcastTranscriptEntry, PodcastTranscripts, State
from .utils import get_voice_for_provider


async def create_podcast_transcript(
    state: State, config: RunnableConfig
) -> dict[str, Any]:
    """Each node does work."""

    # Get configuration from runnable config
    configuration = Configuration.from_runnable_config(config)
    user_id = configuration.user_id
    search_space_id = configuration.search_space_id

    # Get user's long context LLM
    llm = await get_user_long_context_llm(state.db_session, user_id, search_space_id)
    if not llm:
        error_message = f"No long context LLM configured for user {user_id} in search space {search_space_id}"
        print(error_message)
        raise RuntimeError(error_message)

    # Get the prompt
    prompt = get_podcast_generation_prompt()

    # Create the messages
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(
            content=f"<source_content>{state.source_content}</source_content>"
        ),
    ]

    # Generate the podcast transcript
    llm_response = await llm.ainvoke(messages)

    # First try the direct approach
    try:
        podcast_transcript = PodcastTranscripts.model_validate(
            json.loads(llm_response.content)
        )
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Direct JSON parsing failed, trying fallback approach: {e!s}")

        # Fallback: Parse the JSON response manually
        try:
            # Extract JSON content from the response
            content = llm_response.content

            # Find the JSON in the content (handle case where LLM might add additional text)
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]

                # Parse the JSON string
                parsed_data = json.loads(json_str)

                # Convert to Pydantic model
                podcast_transcript = PodcastTranscripts.model_validate(parsed_data)

                print("Successfully parsed podcast transcript using fallback approach")
            else:
                # If JSON structure not found, raise a clear error
                error_message = f"Could not find valid JSON in LLM response. Raw response: {content}"
                print(error_message)
                raise ValueError(error_message)

        except (json.JSONDecodeError, ValueError) as e2:
            # Log the error and re-raise it
            error_message = f"Error parsing LLM response (fallback also failed): {e2!s}"
            print(f"Error parsing LLM response: {e2!s}")
            print(f"Raw response: {llm_response.content}")
            raise

    return {"podcast_transcript": podcast_transcript.podcast_transcripts}


async def create_merged_podcast_audio(
    state: State, config: RunnableConfig
) -> dict[str, Any]:
    """Generate audio for each transcript and merge them into a single podcast file."""

    configuration = Configuration.from_runnable_config(config)

    starting_transcript = PodcastTranscriptEntry(
        speaker_id=1, dialog=f"Welcome to {configuration.podcast_title} Podcast."
    )

    transcript = state.podcast_transcript

    # Merge the starting transcript with the podcast transcript
    # Check if transcript is a PodcastTranscripts object or already a list
    if hasattr(transcript, "podcast_transcripts"):
        transcript_entries = transcript.podcast_transcripts
    else:
        transcript_entries = transcript

    merged_transcript = [starting_transcript, *transcript_entries]

    # Create a temporary directory for audio files
    temp_dir = Path("temp_audio")
    temp_dir.mkdir(exist_ok=True)

    # Generate a unique session ID for this podcast
    session_id = str(uuid.uuid4())
    output_path = f"podcasts/{session_id}_podcast.mp3"
    os.makedirs("podcasts", exist_ok=True)

    # Generate audio for each transcript segment
    audio_files = []

    async def generate_speech_for_segment(segment, index):
        # Handle both dictionary and PodcastTranscriptEntry objects
        if hasattr(segment, "speaker_id"):
            speaker_id = segment.speaker_id
            dialog = segment.dialog
        else:
            speaker_id = segment.get("speaker_id", 0)
            dialog = segment.get("dialog", "")

        # Select voice based on speaker_id
        voice = get_voice_for_provider(app_config.TTS_SERVICE, speaker_id)

        # Generate a unique filename for this segment
        if app_config.TTS_SERVICE == "local/kokoro":
            # Kokoro generates WAV files
            filename = f"{temp_dir}/{session_id}_{index}.wav"
        else:
            # Other services generate MP3 files
            filename = f"{temp_dir}/{session_id}_{index}.mp3"

        try:
            if app_config.TTS_SERVICE == "local/kokoro":
                # Use Kokoro TTS service
                kokoro_service = await get_kokoro_tts_service(
                    lang_code="a"
                )  # American English
                audio_path = await kokoro_service.generate_speech(
                    text=dialog, voice=voice, speed=1.0, output_path=filename
                )
                return audio_path
            else:
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

                # Save the audio to a file - use proper streaming method
                with open(filename, "wb") as f:
                    f.write(response.content)

                return filename
        except Exception as e:
            print(f"Error generating speech for segment {index}: {e!s}")
            raise

    # Generate all audio files concurrently
    tasks = [
        generate_speech_for_segment(segment, i)
        for i, segment in enumerate(merged_transcript)
    ]
    audio_files = await asyncio.gather(*tasks)

    # Merge audio files using ffmpeg
    try:
        # Create FFmpeg instance with the first input
        ffmpeg = FFmpeg().option("y")

        # Add each audio file as input
        for audio_file in audio_files:
            ffmpeg = ffmpeg.input(audio_file)

        # Configure the concatenation and output
        filter_complex = []
        for i in range(len(audio_files)):
            filter_complex.append(f"[{i}:0]")

        filter_complex_str = (
            "".join(filter_complex) + f"concat=n={len(audio_files)}:v=0:a=1[outa]"
        )
        ffmpeg = ffmpeg.option("filter_complex", filter_complex_str)
        ffmpeg = ffmpeg.output(output_path, map="[outa]")

        # Execute FFmpeg
        await ffmpeg.execute()

        print(f"Successfully created podcast audio: {output_path}")

    except Exception as e:
        print(f"Error merging audio files: {e!s}")
        raise
    finally:
        # Clean up temporary files
        for audio_file in audio_files:
            try:
                os.remove(audio_file)
            except Exception as e:
                print(f"Error removing audio file {audio_file}: {e!s}")
                pass

    return {
        "podcast_transcript": merged_transcript,
        "final_podcast_file_path": output_path,
    }
