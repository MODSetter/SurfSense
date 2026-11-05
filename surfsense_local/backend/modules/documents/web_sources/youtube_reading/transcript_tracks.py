"""The one track a source keeps: the spoken language's, a person's before YouTube's own.

YouTube generates its track in the language the video speaks, so that track names
the language. Never a translation: the source holds what was said.
"""

from collections.abc import Iterable

from youtube_transcript_api import Transcript


def chosen_track(tracks: Iterable[Transcript]) -> Transcript | None:
    tracks = list(tracks)
    generated = next((t for t in tracks if t.is_generated), None)
    written = [t for t in tracks if not t.is_generated]
    if generated is None:
        return next(iter(written), None)
    spoken = _language(generated.language_code)
    return next((t for t in written if _language(t.language_code) == spoken), generated)


def _language(code: str) -> str:
    """`en-GB` and `en` are one language."""
    return code.split("-", 1)[0].lower()
