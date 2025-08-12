def get_voice_for_provider(provider: str, speaker_id: int) -> dict | str:
    """
    Get the appropriate voice configuration based on the TTS provider and speaker ID.

    Args:
        provider: The TTS provider (e.g., "openai/tts-1", "vertex_ai/test")
        speaker_id: The ID of the speaker (0-5)

    Returns:
        Voice configuration - string for OpenAI, dict for Vertex AI
    """
    # Extract provider type from the model string
    provider_type = (
        provider.split("/")[0].lower() if "/" in provider else provider.lower()
    )

    if provider_type == "openai":
        # OpenAI voice mapping - simple string values
        openai_voices = {
            0: "alloy",  # Default/intro voice
            1: "echo",  # First speaker
            2: "fable",  # Second speaker
            3: "onyx",  # Third speaker
            4: "nova",  # Fourth speaker
            5: "shimmer",  # Fifth speaker
        }
        return openai_voices.get(speaker_id, "alloy")

    elif provider_type == "vertex_ai":
        # Vertex AI voice mapping - dict with languageCode and name
        vertex_voices = {
            0: {
                "languageCode": "en-US",
                "name": "en-US-Studio-O",
            },
            1: {
                "languageCode": "en-US",
                "name": "en-US-Studio-M",
            },
            2: {
                "languageCode": "en-UK",
                "name": "en-UK-Studio-A",
            },
            3: {
                "languageCode": "en-UK",
                "name": "en-UK-Studio-B",
            },
            4: {
                "languageCode": "en-AU",
                "name": "en-AU-Studio-A",
            },
            5: {
                "languageCode": "en-AU",
                "name": "en-AU-Studio-B",
            },
        }
        return vertex_voices.get(speaker_id, vertex_voices[0])

    else:
        # Default fallback to OpenAI format for unknown providers
        default_voices = {
            0: "alloy",
            1: "echo",
            2: "fable",
            3: "onyx",
            4: "nova",
            5: "shimmer",
        }
        return default_voices.get(speaker_id, "alloy")
