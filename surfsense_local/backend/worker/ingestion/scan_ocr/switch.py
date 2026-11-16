"""SURFSENSE_LOCAL_SCAN_OCR: which OCR reads a scan or a photo before Docling.

auto      the reader measured best here: Apple's Vision on a Mac, RapidOCR alone
          everywhere else
rapidocr  RapidOCR alone, Docling's own OCR without its layout and table models
off       Docling reads every scan and photo whole, as before
"""

import logging
from enum import StrEnum

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


class ScanOcr(StrEnum):
    AUTO = "auto"
    RAPIDOCR = "rapidocr"
    OFF = "off"


class ScanOcrSettings(BaseSettings):
    """An escape hatch back to Docling, should OCR-first misread scans."""

    model_config = SettingsConfigDict(env_prefix="SURFSENSE_LOCAL_")

    scan_ocr: ScanOcr = ScanOcr.AUTO

    @field_validator("scan_ocr", mode="before")
    @classmethod
    def _any_case(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


def scan_ocr_choice() -> ScanOcr:
    # Not cached: tests flip it per case, and it costs microseconds per file.
    try:
        return ScanOcrSettings().scan_ocr
    except ValidationError:
        # Whoever set the switch most likely meant to turn this reader off.
        log.warning("SURFSENSE_LOCAL_SCAN_OCR is not auto, rapidocr or off: off")
        return ScanOcr.OFF
