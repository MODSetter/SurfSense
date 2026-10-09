"""The ladder results the capability list is written from.

One file per suite version, under `ladder/`. Its shape, so the matrix runner's
`results.json` can be mapped onto it:

    {
      "suite": "create-and-edit", "suite_version": 1, "provisional": true,
      "source": "where the runs are written up",
      "cases": {"smoke": {"image_only": false, "required": true}, ...},
      "models": [{
        "model_id": "claude-haiku-4-5",      # the id the runs sent
        "provider": "anthropic",             # the catalog provider of the connection
        "host": "api.anthropic.com",         # where the requests went
        "served": "remote",                  # "local" for llama.cpp on this computer
        "date": "2026-10-04",
        "reads_images": true,                # as the app declared it for the runs
        "note": "One line on what decided the level.",
        "also": [],                          # other canonical keys for the same model
        "cases": {"smoke": "pass", "board-pack": "fail:skipped_preview_check", ...}
      }]
    }

A case's outcome is `pass`, `fail`, `fail:<behaviour>` (one of FAILURES,
08's grouping of what decided the case), `n/a` (the case does not apply, such
as images on a text-only model) or `not_run` (a gate stopped the column).
Every case of the suite has an outcome. From a run folder's `result.json`,
`outcome` gives pass or fail; the behaviour is the reviewer's triage label.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

# 08-model-ladder-results.md, "What the failures point to".
FAILURES = frozenset(
    {
        "skipped_preview_check",
        "retyped_preview_path",
        "left_out_artifact_id",
        "wrong_tool_arguments",
        "made_no_document",
        "no_citation_marker",
        "text_only",
        "left_image_out",
        "looped",
        "did_not_say_assumption",
    }
)
_PLAIN = frozenset({"pass", "fail", "n/a", "not_run"})


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Needs the model to read an image; a text-only model is not held to it.
    image_only: bool = False
    # Must pass for the agent, whatever the rest score.
    required: bool = False


class ModelResults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str
    provider: str
    host: str
    served: Literal["remote", "local"] = "remote"
    date: date
    reads_images: bool
    note: str
    also: list[str] = []
    cases: dict[str, str]

    @field_validator("cases")
    @classmethod
    def _outcomes(cls, cases: dict[str, str]) -> dict[str, str]:
        for case, outcome in cases.items():
            kind, _, behaviour = outcome.partition(":")
            known = outcome in _PLAIN or (kind == "fail" and behaviour in FAILURES)
            if not known:
                raise ValueError(f"{case}: unknown outcome {outcome!r}")
        return cases

    def failures(self) -> set[str]:
        """The behaviours that decided its failed cases."""
        return {
            outcome.partition(":")[2]
            for outcome in self.cases.values()
            if outcome.startswith("fail:")
        }


class LadderResults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite: str
    suite_version: int
    provisional: bool
    source: str
    cases: dict[str, Case]
    models: list[ModelResults]

    @model_validator(mode="after")
    def _every_case_once(self) -> "LadderResults":
        for model in self.models:
            if set(model.cases) != set(self.cases):
                raise ValueError(
                    f"{model.model_id}: outcomes must cover exactly the suite's cases"
                )
        return self
