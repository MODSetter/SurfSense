"""From the language intent to the locale a request names, and from the locale
tags Nemotron writes after each sentence back to a language code.

`/details` reports only a language the request named, so with
`keep_language_tags` the text itself says what the model heard. A sentence
with no closing punctuation comes back untagged: a third of the measured ones.
"""

import re

from modules.llm.catalog.local.engines.audiocpp.manifest_fields import (
    TranscriptionDefaults,
)
from modules.llm.transcription.language_intent import AUTO
from modules.llm.transcription.written_script import language_by_script

__all__ = ["heard", "requested_locale"]

# `<es-ES>`, `<zh-CN>`: the family's locales, each after a sentence.
_TAG = re.compile(r"\s*<([a-z]{2,3})-[A-Za-z]{2,4}>")


def requested_locale(intent: str, transcription: TranscriptionDefaults) -> str | None:
    """The locale the family takes for the intent; None lets the model detect."""
    if intent == AUTO or intent not in transcription.languages:
        return None
    return transcription.family_codes.get(intent, intent)


def heard(
    text: str, intent: str, transcription: TranscriptionDefaults
) -> tuple[str, str | None]:
    """The text without its tags, and the language of the last one. With no
    tag the language is the intent, or under auto the one its script names."""
    known = {*transcription.languages, *transcription.detected_only}
    bases = _TAG.findall(text)
    stripped = _TAG.sub("", text).strip()
    if bases:
        return stripped, bases[-1] if bases[-1] in known else None
    if intent != AUTO and intent in transcription.languages:
        return stripped, intent
    return stripped, language_by_script(stripped, known)
