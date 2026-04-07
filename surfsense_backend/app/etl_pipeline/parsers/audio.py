from litellm import atranscription

from app.config import config as app_config


async def transcribe_audio(file_path: str, filename: str) -> str:
    stt_service_type = (
        "local"
        if app_config.STT_SERVICE and app_config.STT_SERVICE.startswith("local/")
        else "external"
    )

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
