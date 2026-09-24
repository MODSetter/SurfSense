from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, ValidationError
from sqlalchemy.orm import Session

from modules.llm.providers.protocols import Voice
from modules.llm.resolution import resolve_text_to_speech

MAX_SPEAKERS = 6
DEFAULT_LANGUAGE = "en-US"


class Style(StrEnum):
    CONVERSATIONAL = "conversational"
    INTERVIEW = "interview"
    DEBATE = "debate"
    MONOLOGUE = "monologue"
    NARRATIVE = "narrative"


class Role(StrEnum):
    HOST = "host"
    COHOST = "cohost"
    GUEST = "guest"
    EXPERT = "expert"
    NARRATOR = "narrator"


class Duration(StrEnum):
    SHORT = "short"
    STANDARD = "standard"
    LONG = "long"


# Target length per preset; bounded because voicing runs on this CPU.
MINUTES = {Duration.SHORT: 3, Duration.STANDARD: 8, Duration.LONG: 15}

# Roles by slot when the user has not named the speakers yet.
_ROLE_BY_SLOT = (Role.HOST, Role.GUEST, Role.EXPERT, Role.COHOST, Role.NARRATOR)

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)
]


class Speaker(BaseModel):
    name: Name
    role: Role
    voice: str


class PodcastBrief(BaseModel):
    """The reviewed plan for one episode; stored as the job's options."""

    language: str
    style: Style = Style.CONVERSATIONAL
    duration: Duration = Duration.STANDARD
    speakers: list[Speaker] = Field(min_length=1, max_length=MAX_SPEAKERS)


def default_language(voices: list[Voice]) -> str:
    """American English where a voice speaks it, else any English, else the
    first language the model's roster names: Kitten lists English as `en`."""
    spoken = [language for voice in voices for language in voice.languages]
    if DEFAULT_LANGUAGE in spoken:
        return DEFAULT_LANGUAGE
    english = [language for language in spoken if language.split("-")[0] == "en"]
    return (english or spoken or [DEFAULT_LANGUAGE])[0]


def proposed(voices: list[Voice], language: str | None = None) -> PodcastBrief:
    """The defaults the form opens with: two speakers in a language they speak."""
    language = language or default_language(voices)
    spoken = [voice for voice in voices if language in voice.languages][:2]
    return PodcastBrief(
        language=language,
        speakers=[
            Speaker(name=_default_name(slot), role=_ROLE_BY_SLOT[slot], voice=voice.id)
            for slot, voice in enumerate(spoken)
        ],
    )


def validate_options(session: Session, raw: dict | None) -> dict:
    """The Format hook: the brief, checked against the chosen model's voices."""
    return validated(resolve_text_to_speech(session).voices(), raw).model_dump(
        mode="json"
    )


def validated(voices: list[Voice], raw: dict | None) -> PodcastBrief:
    """The brief a job may run with; raises ValueError with one readable line."""
    if raw is None:
        return proposed(voices)
    try:
        brief = PodcastBrief.model_validate(raw)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise ValueError(f"{location}: {first['msg']}") from error

    by_id = {voice.id: voice for voice in voices}
    for speaker in brief.speakers:
        voice = by_id.get(speaker.voice)
        if voice is None or brief.language not in voice.languages:
            raise ValueError(f"{speaker.name}: pick a {brief.language} voice")
    if len({speaker.voice for speaker in brief.speakers}) < len(brief.speakers):
        raise ValueError("each speaker needs their own voice")
    return brief


def _default_name(slot: int) -> str:
    return _ROLE_BY_SLOT[slot].value.replace("cohost", "co-host").title()
