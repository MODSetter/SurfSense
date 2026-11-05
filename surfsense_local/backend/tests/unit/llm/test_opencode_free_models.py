"""OpenCode's live list says which models are free, ahead of any manifest refresh.

Its price field is undocumented, so a list without one falls back to the manifest.
"""

import json
from types import SimpleNamespace

import httpx
import pytest

from modules.agent.model_endpoint.console_refusal import refusal_for
from modules.chat.errors import ChatErrorKind, classify_chat_error
from modules.llm.connections import service
from modules.llm.connections.opencode_free_models import FREE_MODEL_REASON
from modules.llm.connections.service import discover_models
from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider
from modules.llm.providers.types import Message

pytestmark = pytest.mark.unit
ZEN = "https://opencode.ai/inference/openai/v1"
ZEN_CHAT = f"{ZEN}/chat/completions"


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


async def _chat_failure(base_url: str, status: int, body: dict) -> str:
    provider = OpenAICompatibleChatProvider(
        base_url,
        "oc_sk_test",
        transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body)),
    )
    with pytest.raises(httpx.HTTPStatusError) as refused:
        async for _ in provider.chat(
            "typed-free-model", [Message(role="user", content="Hi")]
        ):
            pass
    return str(refused.value)


async def test_chat_explains_the_consoles_403_and_keeps_its_words() -> None:
    """A typed id reaches the Console. A 403 may have another cause, so its words stay."""
    message = await _chat_failure(ZEN, 403, {"error": {"message": "Not allowed"}})

    assert message == f"Not allowed. {FREE_MODEL_REASON}"


async def test_chat_leaves_another_failure_alone() -> None:
    """A wrong key is not a free model."""
    message = await _chat_failure(ZEN, 401, {"error": {"message": "Bad key"}})

    assert message == "Bad key"


async def test_chat_leaves_another_servers_403_alone() -> None:
    """Only OpenCode has this rule."""
    message = await _chat_failure(
        "https://api.openai.com/v1", 403, {"error": {"message": "Not allowed"}}
    )

    assert message == "Not allowed"


def test_the_agent_gets_the_same_explanation() -> None:
    """opencode shows the message in `{"error": {"message": …}}`."""
    body = json.dumps({"error": {"message": "Not allowed"}}).encode()

    status, content = refusal_for(ZEN_CHAT)(403, body)

    assert status == 403
    assert json.loads(content)["error"]["message"] == (
        f"Not allowed. {FREE_MODEL_REASON}"
    )


def test_the_agent_explains_a_403_with_no_message() -> None:
    """A body with no words still gets a reason."""
    _, content = refusal_for(ZEN_CHAT)(403, b"")

    assert FREE_MODEL_REASON in json.loads(content)["error"]["message"]


def test_the_agent_passes_on_another_hosts_403() -> None:
    """Every other model's words reach opencode untouched."""
    body = json.dumps({"error": {"message": "Not allowed"}}).encode()

    assert refusal_for("https://api.openai.com/v1/chat/completions")(403, body) == (
        403,
        body,
    )


def _status_error(url: str, status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", url)
    return httpx.HTTPStatusError(
        "refused", request=request, response=httpx.Response(status, request=request)
    )


def test_chat_asks_for_another_model_rather_than_a_new_key() -> None:
    """The key is fine: a new one would change nothing."""
    kind, _ = classify_chat_error(_status_error(ZEN_CHAT, 403), "openai_compatible")

    assert kind == ChatErrorKind.MODEL_CANNOT_RUN


@pytest.mark.parametrize(
    ("url", "status"),
    [(ZEN_CHAT, 401), ("https://api.openai.com/v1/chat/completions", 403)],
)
def test_chat_still_blames_the_key_elsewhere(url: str, status: int) -> None:
    """A wrong Console key, or another server's 403, is still the key."""
    kind, _ = classify_chat_error(_status_error(url, status), "openai_compatible")

    assert kind == ChatErrorKind.PROVIDER_AUTH
