import time

from litellm import atranscription

from app.config import config as app_config
from app.observability.domains import speech


async def transcribe_audio(file_path: str, filename: str) -> str:
    stt_service_type = (
        "local"
        if app_config.STT_SERVICE and app_config.STT_SERVICE.startswith("local/")
        else "external"
    )
    provider = "local" if stt_service_type == "local" else "litellm"
    model = None if stt_service_type == "local" else app_config.STT_SERVICE

    t0 = time.perf_counter()
    with speech.transcription_span(provider=provider, model=model):
        try:
            if stt_service_type == "local":
                from app.services.stt_service import stt_service

                result = stt_service.transcribe_file(file_path)
                text = result.get("text", "")
                if not text:
                    raise ValueError("Transcription returned empty text")
            else:
                with open(file_path, "rb") as audio_file:
                    kwargs: dict = {
                        "model": app_config.STT_SERVICE,
                        "file": audio_file,
                        "api_key": app_config.STT_SERVICE_API_KEY,
                    }
                    if app_config.STT_SERVICE_API_BASE:
                        kwargs["api_base"] = app_config.STT_SERVICE_API_BASE
                    response = await atranscription(**kwargs)
                    text = response.get("text", "")
                    if not text:
                        raise ValueError("Transcription returned empty text")

            return f"# Transcription of {filename}\n\n{text}"
        finally:
            speech.record_transcription_duration(
                (time.perf_counter() - t0) * 1000, provider=provider, model=model
            )
