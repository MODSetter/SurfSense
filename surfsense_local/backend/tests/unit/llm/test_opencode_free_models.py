"""OpenCode's live list says which models are free, ahead of any manifest refresh.

Its price field is undocumented, so a list without one falls back to the manifest.
"""

from types import SimpleNamespace

import httpx
import pytest

from modules.llm.connections import service
from modules.llm.connections.opencode_free_models import FREE_MODEL_REASON
from modules.llm.connections.service import discover_models

pytestmark = pytest.mark.unit
ZEN = "https://opencode.ai/inference/openai/v1"


def _priced(model: str, price: float) -> dict:
    return {
        "id": model,
        "cost": {"text": {"input": {"price": price}, "output": {"price": price}}},
    }


async def _reasons(
    monkeypatch: pytest.MonkeyPatch, rows: list[dict], provider: str = "opencode"
) -> dict[str, str | None]:
    """Why each listed model is unusable, as discovery decides it."""
    real_client = httpx.AsyncClient

    def client(**kwargs: object) -> httpx.AsyncClient:
        transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json={"data": rows})
        )
        return real_client(**kwargs, transport=transport)

    monkeypatch.setattr(service.httpx, "AsyncClient", client)
    connection = SimpleNamespace(
        base_url=ZEN, api_key="oc_sk_test", catalog_provider=provider
    )
    models = await discover_models(connection)  # type: ignore[arg-type]
    return {model.name: model.unusable_reason for model in models}


async def test_a_free_model_newer_than_the_manifest_is_unusable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Free previews come and go faster than a refresh."""
    reasons = await _reasons(monkeypatch, [_priced("not-in-the-manifest", 0)])

    assert reasons == {"not-in-the-manifest": FREE_MODEL_REASON}


async def test_a_model_that_started_charging_is_usable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The manifest calls big-pickle free; a live price is newer than that."""
    reasons = await _reasons(monkeypatch, [_priced("big-pickle", 1.5)])

    assert reasons == {"big-pickle": None}


@pytest.mark.parametrize("cost", [None, {}, {"text": {"input": {"price": "0"}}}])
async def test_a_list_without_a_readable_price_keeps_the_manifest(
    cost: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A changed or missing field must never fail a listing or unblock a free model."""
    reasons = await _reasons(monkeypatch, [{"id": "big-pickle", "cost": cost}])

    assert reasons == {"big-pickle": FREE_MODEL_REASON}


@pytest.mark.parametrize(
    "row",
    [_priced("beam-free", 0), {"id": "beam-free"}, _priced("not-in-the-manifest", 0)],
)
async def test_a_go_key_can_use_free_models(
    row: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`beam-free` answered a Go key live on 5 Nov 2026, despite the docs' 403."""
    reasons = await _reasons(monkeypatch, [row], "opencode-go")

    assert reasons == {row["id"]: None}


async def test_another_providers_price_means_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only OpenCode refuses its free models outside its own app."""
    reasons = await _reasons(monkeypatch, [_priced("free-tier", 0)], "openrouter")

    assert reasons == {"free-tier": None}
