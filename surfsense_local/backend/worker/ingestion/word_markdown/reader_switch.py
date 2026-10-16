"""SURFSENSE_LOCAL_DOCX_READER: whether a .docx is read here (fast) or by Docling.

A fresh worker's first Word file took 4.4 s through Docling, its import mostly,
and 0.05 s here; the longest reference contract 5.1 s warm, and 0.13 s here.
"""

import logging
from enum import StrEnum

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


class DocxReader(StrEnum):
    FAST = "fast"
    DOCLING = "docling"


class DocxReaderSettings(BaseSettings):
    """An escape hatch back to Docling, should this reader misread files."""

    model_config = SettingsConfigDict(env_prefix="SURFSENSE_LOCAL_")

    docx_reader: DocxReader = DocxReader.FAST

    @field_validator("docx_reader", mode="before")
    @classmethod
    def _any_case(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


def reads_docx_here() -> bool:
    # Not cached: tests flip it per case, and it costs microseconds per file.
    try:
        return DocxReaderSettings().docx_reader is DocxReader.FAST
    except ValidationError:
        # Whoever set the switch most likely meant to turn this reader off.
        log.warning("SURFSENSE_LOCAL_DOCX_READER is not fast or docling: docling")
        return False
