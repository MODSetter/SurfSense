import asyncio
from pathlib import Path

import soundfile as sf
import torch
from kokoro import KPipeline


class KokoroTTSService:
    """Kokoro TTS service for generating speech from text."""

    def __init__(self, lang_code: str = "a"):
        """
        Initialize the Kokoro TTS service.

        Args:
            lang_code: Language code for TTS
                'a' => American English
                'b' => British English
                'e' => Spanish
                'f' => French
                'h' => Hindi
                'i' => Italian
                'j' => Japanese
                'p' => Brazilian Portuguese
                'z' => Mandarin Chinese
        """
        self.lang_code = lang_code
        self.pipeline = None
        self._initialize_pipeline()

    def _initialize_pipeline(self):
        """Initialize the Kokoro pipeline."""
        try:
            self.pipeline = KPipeline(lang_code=self.lang_code)
        except Exception as e:
            print(f"Error initializing Kokoro pipeline: {e}")
            raise

    async def generate_speech(
        self,
        text: str,
        voice: str = "af_heart",
        speed: float = 1.0,
        output_path: str | None = None,
    ) -> str:
        """
        Generate speech from text using Kokoro TTS.

        Args:
            text: Text to convert to speech
            voice: Voice to use (e.g., "af_heart")
            speed: Speech speed (default: 1.0)
            output_path: Path to save the audio file. If None, creates a temporary file.

        Returns:
            Path to the generated audio file
        """
        if not self.pipeline:
            raise RuntimeError("Kokoro pipeline not initialized")

        try:
            # If no output path provided, create a temporary file
            if output_path is None:
                temp_dir = Path("temp_audio")
                temp_dir.mkdir(exist_ok=True)
                output_path = str(temp_dir / f"kokoro_output_{id(text)}.wav")

            # Ensure output directory exists
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Handle voice tensor loading if it's a path to a .pt file
            voice_param = voice
            if isinstance(voice, str) and voice.endswith(".pt"):
                try:
                    voice_param = torch.load(voice, weights_only=True)
                except Exception as e:
                    print(
                        f"Warning: Could not load voice tensor from {voice}, using default: {e}"
                    )
                    voice_param = "af_heart"

            # Generate audio using the pipeline
            # Run in thread pool since Kokoro is synchronous
            loop = asyncio.get_event_loop()
            generator = await loop.run_in_executor(
                None,
                lambda: self.pipeline(
                    text, voice=voice_param, speed=speed, split_pattern=r"\n+"
                ),
            )

            # Collect all audio segments
            audio_segments = []
            for _i, (_gs, _ps, audio) in enumerate(generator):
                audio_segments.append(audio)

            # Concatenate all audio segments if there are multiple
            if len(audio_segments) > 1:
                import numpy as np

                final_audio = np.concatenate(audio_segments)
            elif len(audio_segments) == 1:
                final_audio = audio_segments[0]
            else:
                raise ValueError("No audio generated from text")

            # Save the audio file
            sf.write(output_path, final_audio, 24000)  # Kokoro uses 24kHz sample rate

            return output_path

        except Exception as e:
            print(f"Error generating speech with Kokoro: {e}")
            raise


# Global instance for reuse
_kokoro_service: KokoroTTSService | None = None


async def get_kokoro_tts_service(lang_code: str = "a") -> KokoroTTSService:
    """
    Get or create a Kokoro TTS service instance.

    Args:
        lang_code: Language code for TTS

    Returns:
        KokoroTTSService instance
    """
    global _kokoro_service

    if _kokoro_service is None or _kokoro_service.lang_code != lang_code:
        _kokoro_service = KokoroTTSService(lang_code=lang_code)

    return _kokoro_service
