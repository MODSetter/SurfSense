"""What an account offers, against stubs shaped as the live API answered."""

import httpx
import pytest

from modules.llm.providers.elevenlabs.account import (
    ElevenLabsRefusedError,
    account_voices,
    text_to_speech_models,
    verify_key,
)

pytestmark = pytest.mark.unit

BASE = "https://api.elevenlabs.io"
MODELS = [
    {
        "model_id": "eleven_v4",
        "name": "Eleven v4",
        "can_do_text_to_speech": True,
        "languages": [{"language_id": "en", "name": "English"}],
    },
    {
        "model_id": "eleven_flash_v2",
        "name": "Eleven Flash v2",
        "can_do_text_to_speech": True,
        "languages": [{"language_id": "en", "name": "English"}],
    },
    # Deprecated by ElevenLabs, yet listed with no flag saying so.
    {"model_id": "eleven_turbo_v2_5", "can_do_text_to_speech": True, "languages": []},
    {"model_id": "eleven_turbo_v2", "can_do_text_to_speech": True, "languages": []},
    {"model_id": "eleven_english_sts_v2", "can_do_text_to_speech": False},
]


def voice(id: str, name: str, category: str, gender: str, owner: bool = False) -> dict:
    """A `/v2/voices` entry."""
    return {
        "voice_id": id,
        "name": name,
        "category": category,
        "is_owner": owner,
        "labels": {"gender": gender},
    }


TALIA = voice("talia", "Talia", "professional", "female")
SARAH = voice("sarah", "Sarah", "premade", "female")
RIVER = voice("river", "River", "premade", "neutral")
MINE = voice("mine", "My clone", "cloned", "male", owner=True)


def server(tier: str | None = "free", voices: list[dict] | None = None):
    """An account's three read routes; a `None` tier lacks `user_read`."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/models":
            return httpx.Response(200, json=MODELS)
        if path == "/v2/voices":
            return httpx.Response(
                200,
                json={
                    "voices": [TALIA, SARAH, RIVER, MINE] if voices is None else voices,
                    "has_more": False,
                },
            )
        if path == "/v1/user/subscription" and tier:
            return httpx.Response(200, json={"tier": tier})
        return httpx.Response(
            401,
            json={
                "detail": {
                    "status": "missing_permissions",
                    "message": "missing the permission user_read",
                }
            },
        )

    return httpx.MockTransport(handler)


def test_only_models_that_voice_text_and_are_not_retired_are_offered() -> None:
    """Deprecated Turbo models are listed with no flag, so they are named here."""
    models = text_to_speech_models(BASE, "k", transport=server())

    assert [model.id for model in models] == ["eleven_v4", "eleven_flash_v2"]
    assert models[0].languages == ("en",)


def test_a_refused_model_list_raises_for_the_listing_to_report() -> None:
    """Reported by status code as any server's failed listing."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": {"message": "Invalid API key"}})

    with pytest.raises(httpx.HTTPStatusError):
        text_to_speech_models(BASE, "k", transport=httpx.MockTransport(handler))


def test_a_free_account_is_not_offered_voices_it_would_be_refused() -> None:
    """Free accounts get a 402 on Voice Library voices their own list carries, and a
    brief preselects the first two, so the script would be written and then fail."""
    voices = account_voices(BASE, "k", ("en",), transport=server("free"))

    assert [v.id for v in voices] == ["mine", "sarah", "river"]


def test_a_paid_account_is_offered_them_after_its_own_and_the_premade() -> None:
    """A paid plan may use them, and the sure voices still come first."""
    voices = account_voices(BASE, "k", (), transport=server("creator"))

    assert [v.id for v in voices] == ["mine", "sarah", "river", "talia"]


def test_an_unknown_tier_keeps_them_since_the_refusal_explains_itself() -> None:
    """`user_read` is optional, and hiding voices on a paid plan would be worse."""
    voices = account_voices(BASE, "k", (), transport=server(None))

    assert [v.id for v in voices] == ["mine", "sarah", "river", "talia"]


def test_a_voice_carries_its_name_gender_and_the_models_languages() -> None:
    """What a brief groups and filters by."""
    by_id = {
        v.id: v for v in account_voices(BASE, "k", ("en", "de"), transport=server())
    }

    assert by_id["sarah"].label == "Sarah"
    assert by_id["sarah"].gender == "female"
    assert by_id["sarah"].languages == ("en", "de")
    # The interface groups by female and male only.
    assert by_id["river"].gender is None


def test_every_page_of_voices_is_read() -> None:
    """A page holds at most 100, and an account can hold more."""
    tokens: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path != "/v2/voices":
            return httpx.Response(200, json={"tier": "creator"})
        assert request.url.params["page_size"] == "100"
        token = request.url.params.get("next_page_token")
        tokens.append(token)
        if token is None:
            return httpx.Response(
                200, json={"voices": [SARAH], "has_more": True, "next_page_token": "2"}
            )
        return httpx.Response(200, json={"voices": [RIVER], "has_more": False})

    voices = account_voices(BASE, "k", (), transport=httpx.MockTransport(handler))

    assert tokens == [None, "2"]
    assert [v.id for v in voices] == ["sarah", "river"]


def test_a_key_that_reads_models_and_voices_is_accepted() -> None:
    """The two reads a picker needs, neither of which spends credits."""
    seen: list[httpx.Request] = []
    inner = server()

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return inner.handler(request)

    verify_key(BASE, "secret", transport=httpx.MockTransport(handler))

    assert {r.url.path for r in seen} == {"/v1/models", "/v2/voices"}
    assert seen[0].headers["xi-api-key"] == "secret"


@pytest.mark.parametrize(
    "missing", ["/v1/models", "/v2/voices"], ids=["models_read", "voices_read"]
)
def test_a_key_missing_a_permission_is_refused_in_elevenlabs_words(
    missing: str,
) -> None:
    """A 401 either way, but its message names the permission to turn on."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == missing:
            return httpx.Response(
                401,
                json={
                    "detail": {
                        "code": "unauthorized",
                        "status": "missing_permissions",
                        "message": "The API key is missing the permission x_read.",
                    }
                },
            )
        return httpx.Response(200, json=[] if "models" in request.url.path else {})

    with pytest.raises(ElevenLabsRefusedError, match="missing the permission x_read"):
        verify_key(BASE, "k", transport=httpx.MockTransport(handler))


def test_an_unreachable_server_is_refused_in_words_too() -> None:
    """A form has only a sentence to show."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(ElevenLabsRefusedError, match="could not be reached"):
        verify_key(BASE, "k", transport=httpx.MockTransport(handler))
