"""Wiring the catalog service once per process."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from modules.llm.catalog.manifest import (
    CuratedModelsManifest,
    load_curated_models,
)
from modules.llm.catalog.service import CatalogService
from shared.config import get_llm_settings


@lru_cache
def get_catalog_service() -> CatalogService:
    settings = get_llm_settings()
    try:
        manifest = load_curated_models()
    except (OSError, ValueError):
        # A broken manifest must not take the screen down: installed models and
        # a local .gguf import still work without it.
        manifest = CuratedModelsManifest(schema_version=3, models=[])
    models_dir = settings.llamacpp_models_dir or Path("models")
    return CatalogService(
        manifest,
        models_dir,
        settings.llamacpp_library_dir or Path("."),
        settings.llamacpp_base_url,
    )


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
