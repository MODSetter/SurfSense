"""Which bundled engine runs which model type, and what each reads from a
manifest entry."""

from collections.abc import Iterable
from dataclasses import dataclass

from modules.llm.catalog.local.engines import sdcpp
from modules.llm.catalog.local.engines.llamacpp import (
    manifest_fields as llamacpp_fields,
)
from modules.llm.catalog.local.engines.sdcpp import manifest_fields as sdcpp_fields
from modules.llm.model_type import ModelType


@dataclass(frozen=True)
class Engine:
    name: str
    runs: ModelType
    entry_owns: frozenset[str]
    entry_requires: frozenset[str]


ENGINES = (
    Engine(
        "llamacpp",
        ModelType.TEXT_GEN,
        llamacpp_fields.ENTRY_OWNS,
        llamacpp_fields.ENTRY_REQUIRES,
    ),
    Engine(
        sdcpp.ENGINE,
        ModelType.IMAGE_GEN,
        sdcpp_fields.ENTRY_OWNS,
        sdcpp_fields.ENTRY_REQUIRES,
    ),
)

ENGINE_ENTRY_FIELDS = frozenset().union(*(e.entry_owns for e in ENGINES))


def engine_for(types: Iterable[ModelType]) -> Engine | None:
    types = set(types)
    return next((e for e in ENGINES if e.runs in types), None)
