"""An ElevenLabs account's voices for a model, and what to say when there are none."""

import hashlib
from dataclasses import dataclass
from typing import Literal

import httpx

from modules.llm.providers.elevenlabs.account import voices_for_model
from modules.llm.providers.elevenlabs.refusal import refusal_message
from modules.llm.voices.voice import Voice

__all__ = ["AccountVoices", "VoicesProblem", "elevenlabs_voices"]

# Held for the process so that a brief outage, or one failed request at Generate,
# does not refuse a brief the voices it picked from were good for.
_held: dict[tuple[int, str, str, str], list[Voice]] = {}


@dataclass(frozen=True)
class VoicesProblem:
    code: Literal["no_usable_voices", "list_failed"]
    message: str


@dataclass(frozen=True)
class AccountVoices:
    voices: list[Voice]
    problem: VoicesProblem | None = None


def elevenlabs_voices(
    connection_id: int, base_url: str, api_key: str | None, model: str
) -> AccountVoices:
    # A digest of the key: an edit keeps the rest, but not the account, and what is
    # held outlives the request, so the key itself is not kept in it.
    account = hashlib.sha256((api_key or "").encode()).hexdigest()
    key = (connection_id, base_url, account, model)
    try:
        voices = voices_for_model(base_url, api_key, model)
    except httpx.HTTPStatusError as error:
        if error.response.is_client_error:
            # A revoked key has to show, so nothing held stands in for it.
            _held.pop(key, None)
            return _failed(refusal_message(error.response))
        return _held_or_failed(key, refusal_message(error.response))
    except (httpx.HTTPError, ValueError):
        return _held_or_failed(key, "ElevenLabs could not be reached.")
    if not voices:
        _held.pop(key, None)
        return AccountVoices(
            [],
            VoicesProblem(
                "no_usable_voices",
                "this ElevenLabs account has no voices its plan can use by API",
            ),
        )
    _held[key] = voices
    return AccountVoices(voices)


def _held_or_failed(key: tuple[int, str, str, str], words: str) -> AccountVoices:
    held = _held.get(key)
    return AccountVoices(held) if held else _failed(words)


def _failed(words: str) -> AccountVoices:
    return AccountVoices([], VoicesProblem("list_failed", words))
