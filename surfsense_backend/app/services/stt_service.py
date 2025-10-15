"""Local Speech-to-Text service using Faster-Whisper."""

import os
import tempfile
from pathlib import Path

from faster_whisper import WhisperModel

from app.config import config


class STTService:
    """Local Speech-to-Text service using Faster-Whisper."""

    def __init__(self):
        """Initialize STT service with model from STT_SERVICE config."""
        # Parse model from STT_SERVICE (e.g., "local/base" or "local/tiny")
        stt_service = config.STT_SERVICE or "local/base"
        if stt_service.startswith("local/"):
            self.model_size = stt_service.split("/", 1)[1]
        else:
            self.model_size = "base"  # fallback
        self._model: WhisperModel | None = None

    def _get_model(self) -> WhisperModel:
        """Lazy load the Whisper model."""
        if self._model is None:
            # Use CPU with optimizations for better performance
            self._model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",  # Quantization for faster CPU inference
                num_workers=1,  # Single worker for stability
            )
        return self._model

    def transcribe_file(self, audio_path: str, language: str | None = None) -> dict:
        """Transcribe audio file to text.

        Args:
            audio_path: Path to audio file
            language: Optional language code (e.g., "en", "es")

        Returns:
            Dict with transcription text and metadata
        """
        model = self._get_model()

        # Transcribe with optimized settings
        segments, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=1,  # Faster inference
            best_of=1,  # Single pass
            temperature=0,  # Deterministic output
            vad_filter=True,  # Voice activity detection
            vad_parameters={"min_silence_duration_ms": 500},
        )

        # Combine all segments
        text = " ".join(segment.text.strip() for segment in segments)

        return {
            "text": text,
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration,
        }

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str | None = None,
    ) -> dict:
        """Transcribe audio from bytes.

        Args:
            audio_bytes: Audio file bytes
            filename: Original filename for format detection
            language: Optional language code

        Returns:
            Dict with transcription text and metadata
        """
        # Save bytes to temporary file
        suffix = Path(filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = tmp_file.name

        try:
            return self.transcribe_file(tmp_path, language)
        finally:
            # Clean up temp file
            os.unlink(tmp_path)


# Global STT service instance
stt_service = STTService()
