from enum import StrEnum

from pydantic import BaseModel, field_validator


class ProcessingMode(StrEnum):
    BASIC = "basic"
    PREMIUM = "premium"

    @classmethod
    def coerce(cls, value: str | None) -> "ProcessingMode":
        if value is None:
            return cls.BASIC
        try:
            return cls(value.lower())
        except ValueError:
            return cls.BASIC

    @property
    def page_multiplier(self) -> int:
        return _PAGE_MULTIPLIERS[self]


_PAGE_MULTIPLIERS: dict["ProcessingMode", int] = {
    ProcessingMode.BASIC: 1,
    ProcessingMode.PREMIUM: 10,
}


class EtlRequest(BaseModel):
    file_path: str
    filename: str
    estimated_pages: int = 0
    processing_mode: ProcessingMode = ProcessingMode.BASIC

    @field_validator("filename")
    @classmethod
    def filename_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("filename must not be empty")
        return v


class EtlResult(BaseModel):
    markdown_content: str
    etl_service: str
    actual_pages: int = 0
    content_type: str
