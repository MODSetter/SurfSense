from collections.abc import Iterable

from modules.llm.model_type import ModelType

# Every type but the embedder, which belongs to the index rather than a selection.
SLOTS = tuple(t for t in ModelType if t is not ModelType.EMBEDDING)


def selectable_for(types: Iterable[ModelType], known: bool) -> list[ModelType]:
    """The slots a model can fill, and the one rule selection and every picker share.

    A model fills the slots of the types it is. One nothing recognises fills
    every slot, because unknown is not no: the user can see it answer before
    trusting it with a slot.
    """
    if not known:
        return list(SLOTS)
    held = set(types)
    return [slot for slot in SLOTS if slot in held]
