"""Which slots a model can fill: the one rule selection and every picker share."""

import pytest

from modules.llm.model_type import ModelType
from modules.llm.selectable import selectable_for

pytestmark = pytest.mark.unit


def test_an_embedder_fills_no_slot() -> None:
    """The embedder belongs to the index, which onboarding fixes once."""
    assert selectable_for((ModelType.EMBEDDING,), known=True) == []


def test_a_model_nothing_recognises_is_never_offered_the_embedding_type() -> None:
    """Unknown is offered every slot, and embedding is not a slot."""
    assert ModelType.EMBEDDING not in selectable_for((), known=False)
    assert ModelType.TEXT_GEN in selectable_for((), known=False)
