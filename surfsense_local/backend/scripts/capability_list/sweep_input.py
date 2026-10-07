"""The OpenRouter screening sweep's results, as its `sweep-results.json` writes them.

    {
      "date": "2026-10-07",                  # optional; else --date
      "models": [{
        "id": "qwen/qwen3.8-27b",            # the id the runs sent
        "key": "qwen3-8-27b",                # its canonical key
        "reads_images": true,
        "status": "done", "level": "below",  # the sweep's verdict
        "smoke": "pass", "pdf_brief": "pass", "board_pack": "fail",
        "passed": 1, "counted": 2, "run": 2,
        "measured_on": "2026-10-07",
        "cost": 0.41, "notes": ["..."]
      }],
      "unfinished": [...],                   # unresolved, running or pending
      "assumed": [{"id": "anthropic/claude-opus-4.6", "key": "claude-opus-4-6",
                   "reads_images": true}]
    }

`smoke`, `cost` and `notes` are the sweep's own record; a row is written from
the counts alone, and only for a model the sweep has a verdict for.
"""

from datetime import date
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from modules.llm.capability.match_key import match_key

# The sweep's one status with a verdict; a row with no status is read by its counts.
DONE = "done"


class SweptModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    key: str
    reads_images: bool
    # `done`, or `unresolved`, `running` and `pending`, which measured nothing.
    status: str | None = None
    # `agent` for both cases passed, `below` otherwise; None while unresolved.
    level: Literal["agent", "below"] | None = None
    smoke: str | bool | None = None
    pdf_brief: str | bool | None = None
    board_pack: str | bool | None = None
    # Of the two cases, PDF brief and Board pack; None until the sweep has a verdict.
    passed: int | None = Field(default=None, ge=0)
    counted: int | None = Field(default=None, ge=0)
    run: int | None = Field(default=None, ge=0)
    # The day the model's last run ended.
    measured_on: date | None = None
    cost: float | None = None
    notes: str | list[str] | None = None

    @property
    def finished(self) -> bool:
        """Whether its counts are a measurement: a provider's 502 is not a failed case."""
        if self.status is not None and (self.status != DONE or self.level is None):
            return False
        return None not in (self.passed, self.counted, self.run)


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
    unfinished: list[SweptModel] = []
    assumed: list[AssumedModel] = []

    def measured(self) -> list[SweptModel]:
        """Models with a verdict, less a variant waiting for its own model's."""
        return [
            model
            for model in self.models
            if model.finished and self.waiting_for(model) is None
        ]

    def waiting_for(self, model: SweptModel) -> SweptModel | None:
        """The model a variant folds into while that one has no verdict.

        Listed first, the variant would hold the model's name, and its score
        would stand for the model's: gpt-5.2-chat waits for gpt-5.2.
        """
        loose = match_key(model.key)
        return next(
            (
                other
                for other in self.left_out()
                if len(other.key) < len(model.key) and match_key(other.key) == loose
            ),
            None,
        )

    def left_out(self) -> list[SweptModel]:
        """Models the sweep has no verdict for, wherever the file lists them."""
        return [
            *(model for model in self.models if not model.finished),
            *self.unfinished,
        ]
