from pydantic import BaseModel, field_validator


class EtlRequest(BaseModel):
    file_path: str
    filename: str
    estimated_pages: int = 0

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
