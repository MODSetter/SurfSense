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
from app.services.llm_service import get_user_long_context_llm

try:
    from app.services.dia_service import get_dia_service, DiaServiceError
    DIA_AVAILABLE = True
except ImportError:
    # Handle case where Dia dependencies are not installed
    DIA_AVAILABLE = False
    DiaServiceError = Exception
    
    def get_dia_service():
        class MockDiaService:
            def is_dia_available(self):
                return False, "Dia dependencies not installed. Install with: pip install -e .[local-tts]"
        return MockDiaService()

from .configuration import Configuration
from .prompts import get_podcast_generation_prompt
from .state import PodcastTranscriptEntry, PodcastTranscripts, State


async def create_podcast_transcript(
    state: State, config: RunnableConfig
) -> dict[str, Any]:
    """Each node does work."""

    # Get configuration from runnable config
    configuration = Configuration.from_runnable_config(config)
    user_id = configuration.user_id

    # Get user's long context LLM
    llm = await get_user_long_context_llm(state.db_session, user_id)
    if not llm:
        error_message = f"No long context LLM configured for user {user_id}"
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


async def create_merged_podcast_audio_with_dia(
    state: State, config: RunnableConfig
) -> dict[str, Any]:
    """Generate audio for podcast using Dia if available, fallback to traditional TTS."""
    
    configuration = Configuration.from_runnable_config(config)
    
    starting_transcript = PodcastTranscriptEntry(
        speaker_id=1, dialog=f"Welcome to {configuration.podcast_title} Podcast."
    )
    
    transcript = state.podcast_transcript
    
    # Check if transcript is a PodcastTranscripts object or already a list
    if transcript is None:
        transcript_entries = []
    elif hasattr(transcript, "podcast_transcripts"):
        transcript_entries = transcript.podcast_transcripts
    elif isinstance(transcript, list):
        transcript_entries = transcript
    else:
        transcript_entries = []
    
    merged_transcript = [starting_transcript, *transcript_entries]
    
    # Generate a unique session ID for this podcast
    session_id = str(uuid.uuid4())
    output_path = f"podcasts/{session_id}_podcast.mp3"
    os.makedirs("podcasts", exist_ok=True)
    
    # Check if Dia is available and should be used
    dia_service = get_dia_service()
    dia_available, dia_message = dia_service.is_dia_available()
    
    if dia_available:
        print(f"Using Dia for podcast generation: {dia_message}")
        return await _generate_audio_with_dia(merged_transcript, output_path, dia_service)
    else:
        print(f"Using traditional TTS: {dia_message}")
        return await _generate_audio_with_traditional_tts(merged_transcript, output_path, session_id)


async def _generate_audio_with_dia(
    merged_transcript: list[PodcastTranscriptEntry], 
    output_path: str, 
    dia_service
) -> dict[str, Any]:
    """Generate audio using Dia TTS."""
    try:
        # Convert transcript to Dia format
        transcript_dicts = []
        for entry in merged_transcript:
            if hasattr(entry, "speaker_id"):
                transcript_dicts.append({
                    "speaker_id": entry.speaker_id,
                    "dialog": entry.dialog
                })
            else:
                transcript_dicts.append(entry)
        
        dia_text = dia_service.convert_podcast_transcript_to_dia_format(transcript_dicts)
        
        # Generate audio with Dia
        dia_service.generate_audio(
            text=dia_text,
            output_path=output_path,
            max_tokens=3072,
            cfg_scale=3.0,
            temperature=1.8,
            top_p=0.90,
            cfg_filter_top_k=45,
            use_torch_compile=False  # Keep False for stability
        )
        
        print(f"Successfully created podcast audio with Dia: {output_path}")
        
        return {
            "podcast_transcript": merged_transcript,
            "final_podcast_file_path": output_path,
        }
        
    except DiaServiceError as e:
        print(f"Dia generation failed, falling back to traditional TTS: {e}")
        # Fall back to traditional TTS
        session_id = str(uuid.uuid4())
        return await _generate_audio_with_traditional_tts(merged_transcript, output_path, session_id)


async def _generate_audio_with_traditional_tts(
    merged_transcript: list[PodcastTranscriptEntry], 
    output_path: str, 
    session_id: str
) -> dict[str, Any]:
    """Generate audio using traditional TTS service (existing implementation)."""
    
    # Create a temporary directory for audio files
    temp_dir = Path("temp_audio")
    temp_dir.mkdir(exist_ok=True)
    
    # Map of speaker_id to voice
    voice_mapping = {
        0: "alloy",  # Default/intro voice
        1: "echo",  # First speaker
        # 2: "fable",  # Second speaker
        # 3: "onyx",   # Third speaker
        # 4: "nova",   # Fourth speaker
        # 5: "shimmer" # Fifth speaker
    }
    
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
        voice = voice_mapping.get(speaker_id, "alloy")
        
        # Generate a unique filename for this segment
        filename = f"{temp_dir}/{session_id}_{index}.mp3"
        
        try:
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
    if transcript is None:
        transcript_entries = []
    elif hasattr(transcript, "podcast_transcripts"):
        transcript_entries = transcript.podcast_transcripts
    elif isinstance(transcript, list):
        transcript_entries = transcript
    else:
        transcript_entries = []

    merged_transcript = [starting_transcript, *transcript_entries]

    # Create a temporary directory for audio files
    temp_dir = Path("temp_audio")
    temp_dir.mkdir(exist_ok=True)

    # Generate a unique session ID for this podcast
    session_id = str(uuid.uuid4())
    output_path = f"podcasts/{session_id}_podcast.mp3"
    os.makedirs("podcasts", exist_ok=True)

    # Map of speaker_id to voice
    voice_mapping = {
        0: "alloy",  # Default/intro voice
        1: "echo",  # First speaker
        # 2: "fable",  # Second speaker
        # 3: "onyx",   # Third speaker
        # 4: "nova",   # Fourth speaker
        # 5: "shimmer" # Fifth speaker
    }

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
        voice = voice_mapping.get(speaker_id, "alloy")

        # Generate a unique filename for this segment
        filename = f"{temp_dir}/{session_id}_{index}.mp3"

        try:
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
