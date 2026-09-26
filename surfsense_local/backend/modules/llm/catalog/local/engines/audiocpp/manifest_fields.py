"""What a curated audio.cpp model commits beyond the shared entry: its voices
and the memory it takes while voicing, because the server reports neither."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from modules.llm.catalog.local.manifest.strict import STRICT


class Voice(BaseModel):
    model_config = STRICT

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    # The form groups voices by it; each model's own voice ids or config say it.
    gender: Literal["female", "male"]
    # None: the voice speaks every language the model lists (Supertonic).
    language: str | None = None


class ChunkStep(BaseModel):
    """A smaller text chunk and the peak it measured, for a tight machine."""

    model_config = STRICT

    text_chunk_size: int = Field(gt=0)
    peak_mb: int = Field(gt=0)


class AudioDefaults(BaseModel):
    model_config = STRICT

    origin: str = Field(min_length=1)
    sample_rate: int = Field(gt=0)
    # Measured on the server with every chunk full, at its default chunk size:
    # the working memory is sized for a request's longest chunk.
    peak_mb: int = Field(gt=0)
    chunk_steps: list[ChunkStep] = Field(default_factory=list)
    languages: list[str] = Field(min_length=1)
    # A podcast gives each of its two speakers a voice.
    voices: list[Voice] = Field(min_length=2)

    @model_validator(mode="after")
    def _voices_hold_together(self) -> "AudioDefaults":
        ids = [v.id for v in self.voices]
        if len(ids) != len(set(ids)):
            raise ValueError("a voice is listed twice")
        stray = {v.language for v in self.voices if v.language} - set(self.languages)
        if stray:
            raise ValueError(f"voices speak unlisted languages: {sorted(stray)}")
        return self


ENTRY_OWNS = frozenset({"audio"})
ENTRY_REQUIRES = frozenset({"audio"})
