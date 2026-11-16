"""The transcription server this API reaches, where Electron runs one: only
the API is told its address."""

from modules.llm.providers.audiocpp.transcription import AudioCppTranscriber
from modules.llm.providers.protocols import Transcriber
from shared.config import get_llm_settings

__all__ = ["transcriber_here", "unload_speech_model"]


def transcriber_here() -> Transcriber | None:
    """None where no audio.cpp is staged."""
    url = get_llm_settings().transcription_base_url
    return AudioCppTranscriber(url) if url else None


async def unload_speech_model(model: str) -> None:
    transcriber = transcriber_here()
    if transcriber is not None:
        await transcriber.unload(model)
