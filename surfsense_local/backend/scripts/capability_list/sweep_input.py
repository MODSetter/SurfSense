"""The OpenRouter screening sweep's results, as its `sweep-results.json` writes them.

    {
      "date": "2026-10-07",                  # optional; else --date, else today
      "models": [{
        "id": "qwen/qwen3.8-27b",            # the id the runs sent
        "key": "qwen3-8-27b",                # its canonical key
        "reads_images": true,
        "smoke": "pass", "pdf_brief": "pass", "board_pack": "fail",
        "passed": 1, "counted": 2, "run": 2,
        "cost": 0.41, "notes": "..."
      }],
      "assumed": [{"id": "anthropic/claude-opus-4.6", "key": "claude-opus-4-6",
                   "reads_images": true}]
    }

`smoke`, `cost` and `notes` are the sweep's own record; a row is written from
the counts alone.
"""

from datetime import date

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class SweptModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    key: str
    reads_images: bool
    smoke: str | bool | None = None
    pdf_brief: str | bool | None = None
    board_pack: str | bool | None = None
    # Of the two cases, PDF brief and Board pack.
    passed: int = Field(ge=0)
    counted: int = Field(ge=0)
    run: int = Field(ge=0)
    cost: float | None = None
    notes: str | list[str] | None = None


class AssumedModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    key: str
    reads_images: bool


class SweepResults(BaseModel):
    model_config = ConfigDict(extra="ignore")

    measured_on: date | None = Field(
        default=None, validation_alias=AliasChoices("date", "measured_on")
    )
    models: list[SweptModel] = Field(
        default=[], validation_alias=AliasChoices("models", "results")
    )
    assumed: list[AssumedModel] = []
