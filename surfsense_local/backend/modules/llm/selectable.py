from collections.abc import Iterable

from modules.llm.model_type import ModelType

# Every type but the embedder, which belongs to the index rather than a selection.
SLOTS = tuple(t for t in ModelType if t is not ModelType.EMBEDDING)
# No remote speech client exists to call a recogniser, so only one on this
# computer fills the slot.
LOCAL_ONLY = frozenset({ModelType.SPEECH_TO_TEXT})
# What a connection, or a model nothing recognises, may fill.
REMOTE_SLOTS = tuple(slot for slot in SLOTS if slot not in LOCAL_ONLY)


def selectable_for(types: Iterable[ModelType], known: bool) -> list[ModelType]:
    """The slots a model can fill, and the one rule selection and every picker share.

    A model fills the slots of the types it is. One nothing recognises fills
    every slot but the local-only ones, because unknown is not no: the user can
    see it answer before trusting it with a slot.
    """
    if not known:
        return list(REMOTE_SLOTS)
    held = set(types)
    return [slot for slot in SLOTS if slot in held]
