"""What the summary reads off the machine, as production wires it."""

from collections.abc import Iterator

import pytest

from modules.usage_statistics import dependencies
from modules.usage_statistics.dependencies import get_machine_readings

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def fresh_process() -> Iterator[None]:
    """Each test starts as a new process would, before the OS was ever asked."""
    get_machine_readings().os_adapter_names.cache_clear()
    yield
    get_machine_readings().os_adapter_names.cache_clear()


def test_the_os_is_asked_for_its_adapters_once_per_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On Windows each ask starts PowerShell, and the first week reads the summary every 5 minutes."""
    asked: list[None] = []

    def os_adapter_names() -> list[str]:
        asked.append(None)
        return ["NVIDIA GeForce RTX 3050"]

    monkeypatch.setattr(dependencies, "os_adapter_names", os_adapter_names)

    for _ in range(3):
        assert get_machine_readings().os_adapter_names() == ("NVIDIA GeForce RTX 3050",)
    assert len(asked) == 1


def test_an_os_reader_that_breaks_is_no_name_not_a_failed_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The summary still answers; the card's maker is then unknown."""

    def breaks() -> list[str]:
        raise RuntimeError("WMI is not running")

    monkeypatch.setattr(dependencies, "os_adapter_names", breaks)

    assert get_machine_readings().os_adapter_names() is None


def test_a_failed_ask_is_tried_again_an_hour_later_not_on_every_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient failure must not leave the card's maker unknown for the whole session."""
    asked: list[None] = []
    answers: list[list[str] | None] = [None, ["AMD Radeon RX 7600"]]
    clock = [1_000.0]

    def os_adapter_names() -> list[str] | None:
        asked.append(None)
        return answers[len(asked) - 1]

    monkeypatch.setattr(dependencies, "os_adapter_names", os_adapter_names)
    monkeypatch.setattr(dependencies, "_monotonic", lambda: clock[0])

    assert get_machine_readings().os_adapter_names() is None
    clock[0] += 3_599
    assert get_machine_readings().os_adapter_names() is None
    assert len(asked) == 1

    clock[0] += 1
    assert get_machine_readings().os_adapter_names() == ("AMD Radeon RX 7600",)
    clock[0] += 7_200
    assert get_machine_readings().os_adapter_names() == ("AMD Radeon RX 7600",)
    assert len(asked) == 2
