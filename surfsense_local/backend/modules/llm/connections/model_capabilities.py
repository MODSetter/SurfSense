"""The reviewed answer to "what kind of model is this id".

OpenAI-compatible endpoints answer `/models` with bare ids, so there is nothing
in a listing to classify by. `model-capabilities.json` is generated offline by
`scripts/fetch_model_capabilities.py`, reviewed, and committed, which keeps the
guessing in a pull request instead of the request path.

A miss returns None, which the caller reports as "unknown" rather than assuming
anything. An empty tuple is different: it means the table knows this model is
neither a chat nor an image model.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 1
KNOWN_CAPABILITIES = frozenset({"completion", "image_generation"})


class CapabilityRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilities: list[str]
    origin: Literal["models.dev", "curated"]

    @model_validator(mode="after")
    def validate_row(self) -> "CapabilityRow":
        unknown = set(self.capabilities) - KNOWN_CAPABILITIES
        if unknown:
            raise ValueError(f"unknown capability: {sorted(unknown)}")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("duplicate capability in row")
        return self


class ModelCapabilitiesManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int
    source: str
    excluded_providers: list[str]
    models: dict[str, CapabilityRow]
    # Provenance for whoever opens the file; the loader ignores it.
    readme: list[str] = Field(default_factory=list, alias="_readme")

    @model_validator(mode="after")
    def validate_manifest(self) -> "ModelCapabilitiesManifest":
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported model-capability schema: {self.schema_version}"
            )
        return self


def load_model_capabilities(path: Path | None = None) -> ModelCapabilitiesManifest:
    manifest_path = path or Path(__file__).with_name("model-capabilities.json")
    return ModelCapabilitiesManifest.model_validate_json(manifest_path.read_text())


@lru_cache
def _table() -> dict[str, tuple[str, ...]]:
    try:
        manifest = load_model_capabilities()
    except (OSError, ValueError) as error:
        # Losing the table costs labels, not function: every model reports
        # "unknown" and stays selectable behind the test dialog.
        LOGGER.warning("model capability catalogue unavailable: %s", error)
        return {}
    return {name: tuple(row.capabilities) for name, row in manifest.models.items()}


def lookup_capabilities(name: str) -> tuple[str, ...] | None:
    """Capabilities for a model id, or None when the catalogue has no row.

    Endpoints disagree on how to spell the same model: OpenAI returns `gpt-5`,
    Gemini returns `models/gemini-3-flash`, gateways return `openai/gpt-5`. The
    full id is tried first so a vendor-scoped row can win, then the last path
    segment. The same two candidates are built for every id, whatever the
    endpoint.
    """
    table = _table()
    for candidate in (name, name.rsplit("/", 1)[-1]):
        row = table.get(candidate)
        if row is not None:
            return row
    return None
