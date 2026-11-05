"""Which voices the chosen audio model offers, and where they came from."""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from modules.egress import service as egress
from modules.llm.models import ProviderConnection, SelectedModel
from modules.llm.providers import audiocpp
from modules.llm.providers.elevenlabs.account import ELEVENLABS
from modules.llm.providers.openai_compatible.published_voices import published_voices
from modules.llm.providers.openai_compatible.voice_list import listed_voices
from modules.llm.resolution import local_speech, selected_audio, stored_connection
from modules.llm.voices.elevenlabs_roster import VoicesProblem, elevenlabs_voices
from modules.llm.voices.saved import saved_voices
from modules.llm.voices.voice import Voice

__all__ = [
    "ServerRoster",
    "SpeechRoster",
    "VoicedBy",
    "server_roster",
    "speech_voices",
    "voices_page",
]

# `published` is a model's list that also voices ids it leaves out, so the user
# can add more; `server` is a server's whole list, which leaves nothing to add.
Source = Literal["local", "server", "published", "saved"]
ServerSource = Literal["server", "published", "saved"]


@dataclass(frozen=True)
class VoicedBy:
    """The server that voices a podcast, named for the brief."""

    server: str
    model: str


@dataclass(frozen=True)
class SpeechRoster:
    """The voices a brief may pick, and where they came from. Empty only for a
    server model with none added yet."""

    voices: list[Voice]
    source: Source
    voiced_by: VoicedBy | None
    # Why a server has no voices to offer, when it is not simply that it lists none.
    problem: VoicesProblem | None = None


@dataclass(frozen=True)
class ServerRoster:
    source: ServerSource
    voices: list[Voice]
    # The ones only the user's adding keeps here, which removing can take away.
    added: list[str]
    problem: VoicesProblem | None = None


def speech_voices(session: Session) -> SpeechRoster:
    selected = selected_audio(session)
    if selected.provider == audiocpp.PROVIDER:
        return SpeechRoster(local_speech(selected).voices(), "local", None)
    connection = stored_connection(session, selected)
    roster = server_roster(session, selected, connection)
    return SpeechRoster(
        roster.voices,
        roster.source,
        VoicedBy(connection.label, selected.name),
        roster.problem,
    )


def server_roster(
    session: Session, selected: SelectedModel, connection: ProviderConnection
) -> ServerRoster:
    """The server's own list when it has one; else the model's, with the voices
    the user added; else those alone. The server is asked only once its host is
    allowed; until then the added voices stand, since reading them reaches nothing.

    Ends the caller's transaction before asking: a slow server would otherwise
    hold SQLite's write lock for its whole answer."""
    saved = saved_voices(selected)
    ask = (connection.id, connection.base_url, connection.api_key)
    model = selected.name
    try:
        egress.require(session, egress.host_destination(connection.base_url))
    except egress.EgressDeniedError:
        return ServerRoster("saved", _by_id(saved), saved)
    native = connection.auth_kind == ELEVENLABS
    session.commit()
    if native:
        return _elevenlabs_roster(*ask, model, saved)
    listed = listed_voices(*ask)
    if listed is not None:
        return ServerRoster("server", listed, [])
    published = published_voices(*ask, model)
    if published is None:
        return ServerRoster("saved", _by_id(saved), saved)
    added = [voice for voice in saved if voice not in published]
    return ServerRoster("published", _by_id([*published, *added]), added)


def _by_id(ids: list[str]) -> list[Voice]:
    """Ids alone: only ElevenLabs states a voice's name, gender or languages."""
    return [Voice(voice, voice, None, ()) for voice in ids]


def _elevenlabs_roster(
    connection_id: int,
    base_url: str,
    api_key: str | None,
    model: str,
    saved: list[str],
) -> ServerRoster:
    """With no list, any voices added stand, and the user can add one."""
    read = elevenlabs_voices(connection_id, base_url, api_key, model)
    if read.problem:
        return ServerRoster("saved", _by_id(saved), saved, read.problem)
    # A voice added while the list was down may be in a brief, so it stays.
    listed = {voice.id for voice in read.voices}
    added = [voice for voice in saved if voice not in listed]
    return ServerRoster("server", [*read.voices, *_by_id(added)], added)


def voices_page(connection: ProviderConnection, model: str) -> str | None:
    """The page that names a model's voices, where its provider documents one:
    OpenRouter's docs send readers to each model's page."""
    if connection.catalog_provider == "openrouter":
        return f"https://openrouter.ai/{model}"
    return None
