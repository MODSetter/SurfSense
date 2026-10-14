"""One clip written down: the locale the intent names, the model's text, the
language its tags say, and the cleanup. The same for a phrase and a window."""

from dataclasses import dataclass

from modules.llm.providers.protocols import Transcriber
from modules.llm.transcription.audio_checks import CheckedAudio
from modules.llm.transcription.cleanup import cleaned
from modules.llm.transcription.languages import heard, requested_locale
from modules.llm.transcription.selected_model import SpeechModel

__all__ = ["Recognised", "recognise"]


@dataclass(frozen=True)
class Recognised:
    text: str
    # A language code, or None when nothing says which.
    language: str | None


async def recognise(
    transcriber: Transcriber, model: SpeechModel, clip: CheckedAudio
) -> Recognised:
    """Call inside a turn of the gate."""
    raw = await transcriber.transcribe(
        model.model_id,
        clip.wav(),
        requested_locale(model.language_intent, model.transcription),
    )
    text, language = heard(raw, model.language_intent, model.transcription)
    return Recognised(cleaned(text, language, clip.seconds), language)
