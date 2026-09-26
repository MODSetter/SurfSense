"""A case: the passages chat would retrieve for a question, and what a good answer holds."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, TypeAdapter, model_validator

CASES_PATH = Path(__file__).with_name("cases.json")


class Passage(BaseModel):
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1)


class Case(BaseModel):
    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    passages: list[Passage] = Field(default_factory=list)
    # The [n] of each passage that holds the answer; empty when none does.
    supporting: list[int] = Field(default_factory=list)
    # Text a correct answer contains, chosen to read the same in any language.
    facts: list[str] = Field(default_factory=list)
    history: list[Turn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _supporting_names_a_passage(self) -> "Case":
        if any(not 1 <= n <= len(self.passages) for n in self.supporting):
            raise ValueError(f"{self.id}: supporting names a passage it does not have")
        return self


def load_cases(path: Path = CASES_PATH) -> list[Case]:
    cases = TypeAdapter(list[Case]).validate_json(path.read_bytes())
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("a case id is listed twice")
    return cases
