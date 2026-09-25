"""Which bundled engine runs which model type, and what each reads from a
manifest entry."""

from collections.abc import Iterable
from dataclasses import dataclass

from modules.llm.catalog.local.engines import audiocpp, sdcpp
from modules.llm.catalog.local.engines.audiocpp import (
    manifest_fields as audiocpp_fields,
)
from modules.llm.catalog.local.engines.llamacpp import (
    manifest_fields as llamacpp_fields,
)
from modules.llm.catalog.local.engines.sdcpp import manifest_fields as sdcpp_fields
from modules.llm.model_type import ModelType


@dataclass(frozen=True)
class Engine:
    name: str
    # The types it runs; the first is the one an install fills unless told.
    runs: tuple[ModelType, ...]
    entry_owns: frozenset[str]
    entry_requires: frozenset[str]
    # Exactly one of these must be present, where the engine has such a choice.
    entry_requires_one_of: frozenset[str] = frozenset()


ENGINES = (
    Engine(
        "llamacpp",
        (ModelType.TEXT_GEN,),
        llamacpp_fields.ENTRY_OWNS,
        llamacpp_fields.ENTRY_REQUIRES,
    ),
    Engine(
        sdcpp.ENGINE,
        (ModelType.IMAGE_GEN, ModelType.IMAGE_EDIT, ModelType.VIDEO_GEN),
        sdcpp_fields.ENTRY_OWNS,
        sdcpp_fields.ENTRY_REQUIRES,
        sdcpp_fields.ENTRY_REQUIRES_ONE_OF,
    ),
    Engine(
        audiocpp.ENGINE,
        (ModelType.AUDIO_GEN,),
        audiocpp_fields.ENTRY_OWNS,
        audiocpp_fields.ENTRY_REQUIRES,
    ),
)

ENGINE_ENTRY_FIELDS = frozenset().union(*(e.entry_owns for e in ENGINES))


def engine_for(types: Iterable[ModelType]) -> Engine | None:
    types = set(types)
    return next((e for e in ENGINES if types.intersection(e.runs)), None)
