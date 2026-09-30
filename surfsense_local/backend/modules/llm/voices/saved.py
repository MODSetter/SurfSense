"""The voices the user added for the audio slot's server model, kept under
`voices` in the selection's settings. Only this module reads or writes it."""

from sqlalchemy.orm import Session

from modules.llm.models import SelectedModel

__all__ = ["forget", "keep", "saved_voices"]

KEY = "voices"


def saved_voices(selected: SelectedModel) -> list[str]:
    voices = (selected.settings or {}).get(KEY)
    return (
        [voice for voice in voices if isinstance(voice, str)]
        if isinstance(voices, list)
        else []
    )


def keep(session: Session, selected: SelectedModel, voice: str) -> None:
    voices = saved_voices(selected)
    if voice not in voices:
        _write(selected, [*voices, voice])
        session.flush()


def forget(session: Session, selected: SelectedModel, voice: str) -> None:
    _write(selected, [kept for kept in saved_voices(selected) if kept != voice])
    session.flush()


def _write(selected: SelectedModel, voices: list[str]) -> None:
    # Reassigned, not mutated: a JSON column tracks assignment only.
    settings = {
        key: value for key, value in (selected.settings or {}).items() if key != KEY
    }
    if voices:
        settings[KEY] = voices
    selected.settings = settings or None
