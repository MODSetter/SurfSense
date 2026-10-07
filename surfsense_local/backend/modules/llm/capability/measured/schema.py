"""The shape of the capability list shipped with the app, checked when it is written and loaded."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from modules.llm.capability.match_key import match_key
from modules.llm.capability.model_key import model_key

SCHEMA_VERSION = 1

Served = Literal["remote", "local"]


class Match(BaseModel):
    """Which selections a row holds for."""

    model_config = ConfigDict(extra="forbid")

    # Canonical keys that name this model, its own key first.
    keys: list[str]
    # Where the model is served: a remote host, this computer, or either.
    served: list[Served]


class Passes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: int
    # Cases held against the model: run, and not needing images a text-only model lacks.
    counted: int
    run: int


class MeasuredModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    match: Match
    level: Literal["agent", "agent_limited", "studio_only"]
    suite: str
    suite_version: int
    measured_on: date
    # The provider and host the runs went through, and the id they sent.
    provider: str
    host: str
    model_id: str
    reads_images: bool
    passes: Passes
    # One line on what decided the level, in English: the model's description.
    note: str

    @model_validator(mode="after")
    def _keys_are_canonical(self) -> "MeasuredModel":
        if not self.match.keys or self.match.keys[0] != self.key:
            raise ValueError(f"{self.key}: match.keys must start with the row's key")
        for key in self.match.keys:
            if model_key(key) != key:
                raise ValueError(f"{key} is not a canonical model key")
        return self


class CapabilityList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    # Screening runs, one per cell, until the committed matrix replaces them.
    provisional: bool
    source: str
    models: list[MeasuredModel]

    @model_validator(mode="after")
    def _one_row_per_key(self) -> "CapabilityList":
        seen: set[str] = set()
        # The looser key too: a local copy's spelling must find one row, not either.
        owners: dict[str, str] = {}
        for row in self.models:
            for key in row.match.keys:
                if key in seen:
                    raise ValueError(f"{key} is matched by two rows")
                seen.add(key)
                loose = match_key(key)
                owner = owners.setdefault(loose, row.key) if loose else row.key
                if owner != row.key:
                    raise ValueError(f"{row.key} and {owner} match the same model")
        return self
