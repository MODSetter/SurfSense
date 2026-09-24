"""Where the bundled sd-server answers, and whether this build ships it. Which
models it runs is the catalog's: `catalog/local/engines/sdcpp/`.
"""

from pathlib import Path

from shared.config import get_llm_settings

PROVIDER = "sdcpp"


def model_dir() -> Path | None:
    return get_llm_settings().image_models_dir


def offered() -> bool:
    """False where Electron staged no sd-server, so nothing is advertised."""
    return model_dir() is not None


def base_url() -> str:
    """Where sd-server answers, once it is running."""
    return f"{get_llm_settings().image_base_url.rstrip('/')}/v1"
