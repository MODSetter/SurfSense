"""Keeping the chosen local model in memory before anyone asks it anything.

A cold load is tens of seconds, and it lands on whoever asks the first
question. These are the two moments the app knows a model is about to be
wanted and nobody is waiting yet.
"""

import pytest

from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.residency import warm_selected
from tests.unit.llm.providers.llamacpp.fake_router import FakeRouter

pytestmark = pytest.mark.unit

MODEL = "Qwen3-1.7B-Q4_K_M"


def selection(provider: str, name: str = MODEL) -> SelectedModel:
    """A chosen model, built without a database: only two fields are read."""
    return SelectedModel(model_type=ModelType.TEXT_GEN, provider=provider, name=name)


async def warm(router: FakeRouter, selected: SelectedModel | None) -> bool:
    """Whether this selection was brought into memory."""
    return await warm_selected(selected, "http://router", transport=router.transport())


async def test_the_chosen_local_model_is_loaded() -> None:
    """The point: the load happens now rather than on the first question."""
    router = FakeRouter(models=[MODEL])

    assert await warm(router, selection("llamacpp")) is True
    assert router.load_calls == [MODEL]


async def test_a_remote_model_never_touches_the_runtime() -> None:
    """Someone answering through their own endpoint runs no local runtime, and
    must not be made to hold a model in memory for one."""
    router = FakeRouter(models=[MODEL])

    assert await warm(router, selection("openai_compatible")) is False
    assert router.load_calls == []


async def test_the_image_model_is_not_a_chat_model() -> None:
    """`sdcpp` answers the image role from its own sidecar. Loading its name
    into the text runtime would evict the model that does answer chat."""
    router = FakeRouter(models=[MODEL])

    assert await warm(router, selection("sdcpp")) is False
    assert router.load_calls == []


async def test_nothing_chosen_yet_is_nothing_to_warm() -> None:
    """First run, before onboarding picks anything."""
    router = FakeRouter()

    assert await warm(router, None) is False
    assert router.load_calls == []


async def test_a_runtime_that_refuses_is_not_an_error() -> None:
    """A selection can outlive the file it names, and the sidecar restarts
    whenever the preset is rewritten, so a warm landing in either window is
    routine. It costs the wait it was avoiding, which is where the caller
    already was."""
    router = FakeRouter(models=[MODEL])

    assert await warm(router, selection("llamacpp", "deleted-since")) is False
