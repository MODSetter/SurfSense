"""Wiring the local catalog service once per process."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from modules.llm.catalog.local.engines.audiocpp.audio_folder.espeak import Espeak
from modules.llm.catalog.local.engines.audiocpp.bundled import bundled_audio_dir
from modules.llm.catalog.local.manifest import empty_manifest, load_local_manifest
from modules.llm.catalog.local.service import LocalCatalogService
from shared.config import get_llm_settings


@lru_cache
def get_local_catalog() -> LocalCatalogService:
    settings = get_llm_settings()
    try:
        manifest = load_local_manifest()
    except (OSError, ValueError):
        # A broken manifest must not take the screen down: downloaded models
        # and search still work without it.
        manifest = empty_manifest()
    return LocalCatalogService(
        manifest,
        settings.llamacpp_models_dir or Path("models"),
        settings.llamacpp_library_dir or Path("."),
        settings.llamacpp_base_url,
        images_dir=settings.image_models_dir,
        audio_dir=settings.audio_models_dir,
        audio_bundled_dir=bundled_audio_dir(),
        audio_espeak=(
            Espeak(settings.audio_espeak_library, settings.audio_espeak_data)
            if settings.audio_espeak_library and settings.audio_espeak_data
            else None
        ),
    )


LocalCatalogDep = Annotated[LocalCatalogService, Depends(get_local_catalog)]
