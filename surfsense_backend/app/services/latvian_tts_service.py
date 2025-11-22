"""
Latvian TTS service using Coqui TTS (Mozilla TTS).
Supports Latvian language text-to-speech synthesis with text preprocessing.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Optional

from pydub import AudioSegment

from app.services.latvian_text_preprocessing import get_latvian_text_preprocessor

logger = logging.getLogger(__name__)


class LatvianTTSService:
    """Service for generating Latvian speech using Coqui TTS."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        output_dir: str = "/tmp/surfsense/tts/latvian",
        cache_dir: str = "/tmp/surfsense/tts/cache",
    ):
        """
        Initialize the Latvian TTS service.

        Args:
            model_name: Name of the TTS model to use. Options:
                        - None (auto-select best available model)
                        - "tts_models/multilingual/multi-dataset/your_tts" (multilingual)
                        - Custom model path
            output_dir: Directory for generated audio files
            cache_dir: Directory for cached audio files
        """
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.cache_dir = Path(cache_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.tts = None
        self.preprocessor = get_latvian_text_preprocessor()

        # Initialize TTS model
        self._initialize_tts()

    def _initialize_tts(self):
        """Initialize the Coqui TTS model."""
        try:
            # Try to import TTS
            from TTS.api import TTS

            # If no model specified, try to find a suitable one
            if self.model_name is None:
                # Check for available models
                available_models = TTS.list_models()

                # Look for Latvian-specific model first
                latvian_models = [m for m in available_models if "lv" in m.lower()]

                if latvian_models:
                    self.model_name = latvian_models[0]
                    logger.info(f"Found Latvian TTS model: {self.model_name}")
                else:
                    # Fall back to multilingual model
                    # YourTTS is a good multilingual model that might work for Latvian
                    multilingual_models = [
                        "tts_models/multilingual/multi-dataset/your_tts",
                        "tts_models/multilingual/multi-dataset/xtts_v2",
                    ]

                    for model in multilingual_models:
                        if model in available_models:
                            self.model_name = model
                            logger.info(
                                f"Using multilingual TTS model: {self.model_name}"
                            )
                            break

            if self.model_name:
                logger.info(f"Initializing TTS model: {self.model_name}")
                self.tts = TTS(model_name=self.model_name)
                logger.info("TTS model initialized successfully")
            else:
                logger.error("No suitable TTS model found for Latvian")

        except ImportError:
            logger.error(
                "Coqui TTS not installed. Install with: pip install TTS"
            )
            self.tts = None
        except Exception as e:
            logger.error(f"Error initializing TTS model: {e}")
            self.tts = None

    def check_tts_available(self) -> bool:
        """
        Check if TTS is available and initialized.

        Returns:
            True if TTS is ready, False otherwise
        """
        return self.tts is not None

    def get_available_speakers(self) -> List[str]:
        """
        Get list of available speakers/voices.

        Returns:
            List of speaker names
        """
        if not self.tts:
            return []

        try:
            # Try to get speakers from the model
            if hasattr(self.tts, "speakers"):
                return list(self.tts.speakers)
            return []
        except Exception as e:
            logger.warning(f"Could not get speaker list: {e}")
            return []

    async def generate_audio(
        self,
        text: str,
        speaker: Optional[str] = None,
        output_path: Optional[str] = None,
        preprocess: bool = True,
    ) -> str:
        """
        Generate audio from Latvian text.

        Args:
            text: Text to convert to speech (in Latvian)
            speaker: Speaker/voice name (if model supports multiple speakers)
            output_path: Path to save the audio file. If None, generates a temp file.
            preprocess: Whether to preprocess text before synthesis

        Returns:
            Path to the generated audio file

        Raises:
            RuntimeError: If TTS is not available
            ValueError: If text is empty or invalid
        """
        if not self.tts:
            raise RuntimeError(
                "TTS is not available. Please check if Coqui TTS is installed "
                "and a suitable model is available."
            )

        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        try:
            # Preprocess text if requested
            if preprocess:
                logger.info("Preprocessing Latvian text...")
                text = await self.preprocessor.preprocess_for_tts(text)

            # Generate output path if not provided
            if output_path is None:
                import hashlib

                text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
                output_path = self.output_dir / f"latvian_tts_{text_hash}.wav"
            else:
                output_path = Path(output_path)

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Generating audio for text: {text[:100]}...")

            # Run TTS generation in thread pool (it's synchronous)
            loop = asyncio.get_event_loop()

            def generate():
                # Build TTS arguments
                tts_kwargs = {"text": text, "file_path": str(output_path)}

                # Add speaker if specified and supported
                if speaker and hasattr(self.tts, "speakers"):
                    if speaker in self.tts.speakers:
                        tts_kwargs["speaker"] = speaker
                    else:
                        logger.warning(
                            f"Speaker '{speaker}' not found in model. Using default."
                        )

                # Add language if the model is multilingual
                if hasattr(self.tts, "languages") and "lv" in self.tts.languages:
                    tts_kwargs["language"] = "lv"

                # Generate audio
                self.tts.tts_to_file(**tts_kwargs)

            await loop.run_in_executor(None, generate)

            logger.info(f"Audio generated successfully: {output_path}")

            return str(output_path)

        except Exception as e:
            logger.error(f"Error generating audio: {e}")
            raise

    async def generate_podcast(
        self,
        sections: List[dict],
        output_path: str,
        pause_between_sections: float = 1.0,
    ) -> str:
        """
        Generate a podcast by combining multiple text sections.

        Args:
            sections: List of dicts with keys:
                     - "text": Text content
                     - "speaker": Optional speaker name
                     - "pause_after": Optional pause duration in seconds (default: 1.0)
            output_path: Path to save the final podcast MP3
            pause_between_sections: Default pause between sections in seconds

        Returns:
            Path to the generated podcast file

        Raises:
            RuntimeError: If TTS is not available
            ValueError: If sections list is empty
        """
        if not self.tts:
            raise RuntimeError("TTS is not available")

        if not sections:
            raise ValueError("Sections list cannot be empty")

        try:
            logger.info(f"Generating podcast with {len(sections)} sections...")

            # Generate audio for each section
            audio_files = []
            for i, section in enumerate(sections):
                text = section.get("text", "")
                speaker = section.get("speaker")

                if not text:
                    continue

                logger.info(f"Generating section {i + 1}/{len(sections)}...")

                # Generate audio for this section
                temp_path = (
                    self.output_dir / f"podcast_section_{i}_{os.getpid()}.wav"
                )
                audio_file = await self.generate_audio(
                    text=text, speaker=speaker, output_path=str(temp_path)
                )

                audio_files.append((audio_file, section.get("pause_after", pause_between_sections)))

            # Combine all audio files
            logger.info("Combining audio sections...")

            combined = None
            pause_ms = int(pause_between_sections * 1000)

            for audio_file, custom_pause in audio_files:
                # Load audio segment
                segment = AudioSegment.from_file(audio_file)

                if combined is None:
                    combined = segment
                else:
                    # Add pause and then the new segment
                    pause_duration = int(custom_pause * 1000)
                    silence = AudioSegment.silent(duration=pause_duration)
                    combined = combined + silence + segment

                # Clean up temporary file
                try:
                    os.unlink(audio_file)
                except Exception as e:
                    logger.warning(f"Could not delete temp file {audio_file}: {e}")

            # Export as MP3
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Exporting podcast to: {output_path}")

            combined.export(
                str(output_path),
                format="mp3",
                bitrate="128k",
                parameters=["-ac", "1"],  # Mono for smaller file size
            )

            logger.info("Podcast generation complete!")

            return str(output_path)

        except Exception as e:
            logger.error(f"Error generating podcast: {e}")
            raise

    def estimate_generation_time(self, text_length: int) -> float:
        """
        Estimate the time required to generate audio for text.

        Args:
            text_length: Length of text in characters

        Returns:
            Estimated time in seconds
        """
        # Rough estimate: ~0.1 seconds per character for TTS processing
        # This is very approximate and depends on hardware
        return text_length * 0.1


# Global instance
_latvian_tts_service: Optional[LatvianTTSService] = None


def get_latvian_tts_service(
    model_name: Optional[str] = None,
) -> LatvianTTSService:
    """
    Get or create the global Latvian TTS service instance.

    Args:
        model_name: Optional TTS model name

    Returns:
        LatvianTTSService instance
    """
    global _latvian_tts_service

    if _latvian_tts_service is None:
        _latvian_tts_service = LatvianTTSService(model_name=model_name)

    return _latvian_tts_service
