def get_voice_for_provider(provider: str, speaker_id: int = 0) -> dict | str:
    """
    Get the appropriate voice configuration based on the TTS provider.

    Currently single-speaker only (speaker_id=0). Multi-speaker support
    will be added in a future iteration.

    Args:
        provider: The TTS provider (e.g., "openai/tts-1", "vertex_ai/test")
        speaker_id: The ID of the speaker (default 0, single speaker for now)

    Returns:
        Voice configuration - string for OpenAI, dict for Vertex AI
    """
    if provider == "local/kokoro":
        return "af_heart"

    provider_type = (
        provider.split("/")[0].lower() if "/" in provider else provider.lower()
    )

    voices = {
        "openai": "alloy",
        "vertex_ai": {
            "languageCode": "en-US",
            "name": "en-US-Studio-O",
        },
        "azure": "alloy",
    }
    return voices.get(provider_type, {})
