"""What an ElevenLabs account offers: its models and its voices, asked live."""

from collections import Counter
from dataclasses import dataclass

import httpx

from modules.llm.providers.elevenlabs.refusal import refusal_message
from modules.llm.voices.voice import Voice

__all__ = [
    "API_URL",
    "ELEVENLABS",
    "ElevenLabsModel",
    "ElevenLabsRefusedError",
    "account_voices",
    "text_to_speech_models",
    "verify_key",
    "voices_for_model",
]

API_URL = "https://api.elevenlabs.io"
# The connection's `auth_kind`: it signs in with `xi-api-key` and speaks this API.
ELEVENLABS = "elevenlabs"

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
# Deprecated in favour of Flash, yet listed with no flag saying so.
_RETIRED = frozenset({"eleven_turbo_v2", "eleven_turbo_v2_5"})
_PAGE_SIZE = 100  # /v2/voices' most.
_MAX_PAGES = 20  # Far past any account seen; a server looping on pages must end.
_VOICE_ID_MAX = 100  # What a voice test and a brief take.
_NEVER_FROM_LIBRARY = frozenset({"premade", "cloned", "generated"})


class ElevenLabsRefusedError(Exception):
    """The key cannot be used, in a sentence naming why."""


@dataclass(frozen=True)
class ElevenLabsModel:
    id: str
    languages: tuple[str, ...]


def _client(
    base_url: str, api_key: str | None, transport: httpx.BaseTransport | None
) -> httpx.Client:
    return httpx.Client(
        base_url=base_url.rstrip("/"),
        timeout=_TIMEOUT,
        headers={"xi-api-key": api_key} if api_key else {},
        transport=transport,
    )


def verify_key(
    base_url: str, api_key: str, *, transport: httpx.BaseTransport | None = None
) -> None:
    """Raise unless the key reads what picking a model and a voice need. Spends no
    credits. `text_to_speech` itself cannot be checked without voicing a line."""
    try:
        with _client(base_url, api_key, transport) as client:
            for path, params, is_answer in (
                ("/v1/models", None, _is_model_list),
                ("/v2/voices", {"page_size": 1}, _is_voice_page),
            ):
                reply = client.get(path, params=params)
                if reply.is_error:
                    raise ElevenLabsRefusedError(refusal_message(reply))
                if not reply.is_success or not is_answer(reply):
                    # A key saved on this could list nothing afterwards.
                    raise ElevenLabsRefusedError(
                        "ElevenLabs answered in a way SurfSense could not read."
                    )
    except httpx.HTTPError as error:
        raise ElevenLabsRefusedError("ElevenLabs could not be reached.") from error


def _is_model_list(reply: httpx.Response) -> bool:
    try:
        return isinstance(reply.json(), list)
    except ValueError:
        return False


def _is_voice_page(reply: httpx.Response) -> bool:
    try:
        page = reply.json()
    except ValueError:
        return False
    return isinstance(page, dict) and isinstance(page.get("voices"), list)


def text_to_speech_models(
    base_url: str,
    api_key: str | None,
    *,
    transport: httpx.BaseTransport | None = None,
) -> list[ElevenLabsModel]:
    """Raises `httpx.HTTPError`, or `ValueError` for a reply that is no list, which
    a model listing reports as any server's."""
    with _client(base_url, api_key, transport) as client:
        reply = client.get("/v1/models")
    reply.raise_for_status()
    entries = reply.json()
    if not isinstance(entries, list):
        raise ValueError("ElevenLabs answered with no model list")
    return [
        ElevenLabsModel(entry["model_id"], _languages(entry))
        for entry in entries
        if isinstance(entry, dict)
        and isinstance(entry.get("model_id"), str)
        and entry.get("can_do_text_to_speech")
        and entry["model_id"] not in _RETIRED
    ]


def _languages(entry: dict) -> tuple[str, ...]:
    listed = entry.get("languages")
    return tuple(
        language["language_id"]
        for language in (listed if isinstance(listed, list) else [])
        if isinstance(language, dict) and isinstance(language.get("language_id"), str)
    )


def account_voices(
    base_url: str,
    api_key: str | None,
    languages: tuple[str, ...],
    *,
    transport: httpx.BaseTransport | None = None,
) -> list[Voice]:
    """The account's voices its plan can use, its own and the premade first, since
    a brief opens on the first two. Each speaks `languages`, its model's: no voice
    is limited to fewer by anything the API enforces."""
    with _client(base_url, api_key, transport) as client:
        entries = _voice_entries(client)
        free = _tier(client) == "free"
    usable = [entry for entry in entries if not (free and _from_library(entry))]
    # Stable, so each group keeps the order ElevenLabs gives it.
    usable.sort(key=_from_library)
    usable.sort(key=lambda entry: not entry.get("is_owner"))
    labels = _distinct_labels(usable)
    return [_voice(entry, labels[entry["voice_id"]], languages) for entry in usable]


def voices_for_model(
    base_url: str,
    api_key: str | None,
    model: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> list[Voice]:
    """`model`'s languages come from its entry; a typed id has none to state."""
    models = text_to_speech_models(base_url, api_key, transport=transport)
    languages = next((m.languages for m in models if m.id == model), ())
    return account_voices(base_url, api_key, languages, transport=transport)


def _voice_entries(client: httpx.Client) -> list[dict]:
    entries: list[dict] = []
    token: str | None = None
    for _ in range(_MAX_PAGES):
        params: dict[str, str | int] = {"page_size": _PAGE_SIZE}
        if token:
            params["next_page_token"] = token
        reply = client.get("/v2/voices", params=params)
        reply.raise_for_status()
        page = reply.json()
        voices = page.get("voices") if isinstance(page, dict) else None
        if not isinstance(voices, list):
            raise ValueError("ElevenLabs answered with no voice list")
        entries.extend(entry for entry in voices if _readable(entry))
        token = page.get("next_page_token")
        if not page.get("has_more") or not token:
            break
    return entries


def _readable(entry: object) -> bool:
    """One odd entry should not cost the user the rest of the list."""
    if not isinstance(entry, dict):
        return False
    voice_id = entry.get("voice_id")
    return isinstance(voice_id, str) and 0 < len(voice_id) <= _VOICE_ID_MAX


def _tier(client: httpx.Client) -> str | None:
    """None without `user_read`, an optional permission."""
    try:
        reply = client.get("/v1/user/subscription")
        return reply.json().get("tier") if reply.is_success else None
    except (httpx.HTTPError, ValueError, AttributeError):
        return None


def _from_library(entry: dict) -> bool:
    """A Voice Library voice, which ElevenLabs refuses Free accounts over the API
    with a 402, though their own list carries the ones they saved. Only Professional
    clones can be shared there, so a clone or generated voice is the account's own,
    even where `is_owner` is null, as the API allows."""
    return entry.get("category") not in _NEVER_FROM_LIBRARY and not entry.get(
        "is_owner"
    )


def _name(entry: dict) -> str:
    return str(entry.get("name") or entry["voice_id"])


def _distinct_labels(entries: list[dict]) -> dict[str, str]:
    """Each voice's label by id. Nothing makes names unique and a picker chooses by
    what it shows, and a name can already read like one told apart by its id."""
    names = Counter(_name(entry) for entry in entries)
    labels = {e["voice_id"]: _name(e) for e in entries if names[_name(e)] == 1}
    taken = set(labels.values())
    for entry in entries:
        voice_id = entry["voice_id"]
        if voice_id in labels:
            continue
        label = f"{_name(entry)} ({voice_id[:8]})"
        if label in taken:
            label = f"{_name(entry)} ({voice_id})"
        labels[voice_id] = label
        taken.add(label)
    return labels


def _voice(entry: dict, label: str, languages: tuple[str, ...]) -> Voice:
    labels = entry.get("labels")
    gender = labels.get("gender") if isinstance(labels, dict) else None
    return Voice(
        entry["voice_id"],
        label,
        # River is `neutral`; the brief groups by these two.
        gender if gender in ("female", "male") else None,
        languages,
    )
