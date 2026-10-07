"""The capability list refuses rows that would be read two ways."""

from typing import Any

import pytest
from pydantic import ValidationError

from modules.llm.capability.measured.schema import CapabilityList, MeasuredModel

pytestmark = pytest.mark.unit


def _row(key: str, **overrides: Any) -> dict[str, Any]:
    return {
        "key": key,
        "match": {"keys": [key], "served": ["remote"]},
        "level": "agent",
        "suite": "openrouter-screen",
        "suite_version": 1,
        "measured_on": "2026-10-07",
        "provider": "openrouter",
        "host": "openrouter.ai",
        "model_id": key,
        "reads_images": True,
        "passes": {"passed": 2, "counted": 2, "run": 2},
        "note": "A note.",
        **overrides,
    }


def _list(*rows: dict[str, Any]) -> CapabilityList:
    return CapabilityList.model_validate(
        {
            "schema_version": 1,
            "provisional": True,
            "source": "test",
            "models": list(rows),
        }
    )


def test_a_key_that_is_not_canonical_is_refused() -> None:
    """A row is found by its canonical key; another spelling would never be read."""
    with pytest.raises(ValidationError):
        MeasuredModel.model_validate(_row("Qwen/Qwen3.8-27B"))


def test_two_rows_for_one_key_are_refused() -> None:
    """Which one holds would depend on the order."""
    with pytest.raises(ValidationError, match="two rows"):
        _list(_row("qwen3-8-27b"), _row("qwen3-8-27b"))


def test_two_rows_one_server_spells_alike_are_refused() -> None:
    """gemma-4-31b and gemma-4-31b-it are the same model to the looser match."""
    with pytest.raises(ValidationError, match="same model"):
        _list(_row("gemma-4-31b-it"), _row("gemma-4-31b"))


def test_rows_for_two_sizes_of_one_model_stand_together() -> None:
    """27B and 14B are two models."""
    assert len(_list(_row("qwen3-8-27b"), _row("qwen3-8-14b")).models) == 2
