"""mc:AlternateContent, read once: from its first choice, which is what Word shows."""

from typing import Any

from worker.ingestion.word_markdown.ooxml_names import MC_CHOICE, MC_FALLBACK


def shown_alternative(alternate: Any) -> Any | None:
    # A choice Word wrote is one it reads; the fallback is for older readers.
    choice = alternate.find(MC_CHOICE)
    return choice if choice is not None else alternate.find(MC_FALLBACK)
