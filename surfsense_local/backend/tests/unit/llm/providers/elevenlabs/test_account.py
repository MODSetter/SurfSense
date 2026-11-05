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


def test_voices_sharing_a_name_can_be_told_apart() -> None:
    """Nothing makes names unique, and a picker chooses by what it shows."""
    voices = [
        voice("premade-id", "Sarah", "premade", "female"),
        voice("clone-id-12345", "Sarah", "cloned", "female", owner=True),
        voice("george-id", "George", "premade", "male"),
    ]

    labels = {
        v.id: v.label
        for v in account_voices(BASE, "k", (), transport=server(voices=voices))
    }

    assert labels["george-id"] == "George"
    assert labels["premade-id"] == "Sarah (premade-)"
    assert labels["clone-id-12345"] == "Sarah (clone-id)"


@pytest.mark.parametrize(
    "body", [{"detail": "not a list"}, "text", 7], ids=["object", "string", "number"]
)
def test_a_model_list_that_is_no_list_is_reported_as_a_bad_answer(body) -> None:
    """A ValueError, which a model listing reports as a 502, not a raw 500."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    with pytest.raises(ValueError, match="model list"):
        text_to_speech_models(BASE, "k", transport=httpx.MockTransport(handler))


def test_a_model_that_cannot_be_read_is_left_out() -> None:
    """One odd entry should not cost the user the rest of the list."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                "junk",
                {"can_do_text_to_speech": True},
                {"model_id": 7, "can_do_text_to_speech": True},
                {
                    "model_id": "eleven_v4",
                    "can_do_text_to_speech": True,
                    "languages": ["junk", {"language_id": "en"}, {"language_id": 7}],
                },
            ],
        )

    models = text_to_speech_models(BASE, "k", transport=httpx.MockTransport(handler))

    assert [(m.id, m.languages) for m in models] == [("eleven_v4", ("en",))]


@pytest.mark.parametrize(
    "body",
    [["a", "list"], {"voices": "not a list"}],
    ids=["page is a list", "voices is a string"],
)
def test_a_voice_page_that_cannot_be_read_is_reported_as_a_bad_answer(body) -> None:
    """A ValueError, which the roster reports rather than crashing on."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    with pytest.raises(ValueError, match="voice list"):
        account_voices(BASE, "k", (), transport=httpx.MockTransport(handler))


def test_a_voice_that_cannot_be_read_is_left_out() -> None:
    """One odd entry should not cost the user the rest of the list."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/voices":
            return httpx.Response(
                200,
                json={
                    "voices": [
                        "junk",
                        {"name": "No id"},
                        {
                            "voice_id": "sarah",
                            "name": "Sarah",
                            "category": "premade",
                            "labels": "not a mapping",
                        },
                    ],
                    "has_more": False,
                },
            )
        return httpx.Response(200, json={"tier": "free"})

    voices = account_voices(BASE, "k", (), transport=httpx.MockTransport(handler))

    assert [(v.id, v.gender) for v in voices] == [("sarah", None)]


def test_a_subscription_reply_that_cannot_be_read_leaves_the_plan_unknown() -> None:
    """It only decides what to hide, so it must not cost the voices."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/voices":
            return httpx.Response(200, json={"voices": [TALIA], "has_more": False})
        return httpx.Response(200, json=["junk"])

    voices = account_voices(BASE, "k", (), transport=httpx.MockTransport(handler))

    assert [v.id for v in voices] == ["talia"]


@pytest.mark.parametrize(
    ("path", "status", "body"),
    [
        ("/v1/models", 302, []),
        ("/v1/models", 200, {"detail": "not a list"}),
        ("/v2/voices", 200, ["not", "an", "object"]),
        ("/v2/voices", 200, {"voices": "not a list"}),
    ],
    ids=["a redirect", "models not a list", "voices not an object", "no voice list"],
)
def test_a_reply_that_proves_nothing_does_not_pass_a_key(path, status, body) -> None:
    """Saving on it would keep a connection that cannot list anything."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == path:
            return httpx.Response(status, json=body)
        if request.url.path == "/v1/models":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"voices": []})

    with pytest.raises(ElevenLabsRefusedError):
        verify_key(BASE, "k", transport=httpx.MockTransport(handler))


def test_a_free_account_keeps_its_own_voices_when_ownership_is_not_stated() -> None:
    """`is_owner` may be null. Only Professional clones reach the library, so a
    cloned or generated voice cannot be one a Free account would be refused."""
    voices = [
        {"voice_id": "clone", "name": "Clone", "category": "cloned", "is_owner": None},
        {"voice_id": "made", "name": "Made", "category": "generated"},
        {
            "voice_id": "lib",
            "name": "Lib",
            "category": "professional",
            "is_owner": False,
        },
        {
            "voice_id": "pro",
            "name": "Pro",
            "category": "professional",
            "is_owner": True,
        },
    ]

    kept = account_voices(BASE, "k", (), transport=server("free", voices))

    assert {v.id for v in kept} == {"clone", "made", "pro"}


def test_a_name_can_already_be_what_telling_two_apart_would_make() -> None:
    """A picker maps a label back to one voice, so every final label must differ."""
    voices = [
        voice("abcdefgh-1", "Sarah", "premade", "female"),
        voice("abcdefgh-2", "Sarah", "premade", "female"),
        voice("other", "Sarah (abcdefgh)", "premade", "female"),
    ]

    labels = [
        v.label for v in account_voices(BASE, "k", (), transport=server(voices=voices))
    ]

    assert len(set(labels)) == 3
    assert "Sarah (abcdefgh)" in labels
