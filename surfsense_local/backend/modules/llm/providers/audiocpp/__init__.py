"""The bundled audio.cpp server: local audio generation, for podcast voices.
Which models it runs is the catalog's: `catalog/local/engines/audiocpp/`.
"""

from shared.config import get_llm_settings

# What a selection names as its provider.
PROVIDER = "audiocpp"


def base_url() -> str:
    """Where audio.cpp's server answers, once Electron has started it."""
    return get_llm_settings().audio_base_url.rstrip("/")
