from collections.abc import Iterable

from modules.llm.model_type import ModelType


def selectable_for(types: Iterable[ModelType], known: bool) -> list[ModelType]:
    """The slots a model can fill, and the one rule selection and every picker share.

    A model fills the slots of the types it is. One nothing recognises fills
    every slot, because unknown is not no: the user can see it answer before
    trusting it with a slot.
    """
    if not known:
        return list(ModelType)
    held = set(types)
    return [model_type for model_type in ModelType if model_type in held]
