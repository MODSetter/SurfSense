"""SURFSENSE_LOCAL_PDF_TEXT_LAYER, an escape hatch should the text layer misread PDFs."""

import logging

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


class TextLayerSettings(BaseSettings):
    """On by default; off sends every PDF to Docling, as before the text layer."""

    model_config = SettingsConfigDict(env_prefix="SURFSENSE_LOCAL_")

    pdf_text_layer: bool = True

    @field_validator("pdf_text_layer", mode="before")
    @classmethod
    def _any_case(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


def text_layer_on() -> bool:
    # Not cached: read once per PDF, so a test or a restart sees a new value.
    try:
        return TextLayerSettings().pdf_text_layer
    except ValidationError:
        # Whoever set the switch most likely meant to turn the text layer off.
        log.warning("SURFSENSE_LOCAL_PDF_TEXT_LAYER is not on or off: off")
        return False
