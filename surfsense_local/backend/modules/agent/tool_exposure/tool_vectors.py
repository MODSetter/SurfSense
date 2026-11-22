"""Tools and requests as vectors, by the embedder SurfSense already runs for search.

A tool's vector is kept for the life of the process: its text changes only when its
plugin's listing does, and embedding one takes about 70 ms on a laptop's CPU.
"""

from sqlalchemy.orm import Session

from modules.embedding import encoder
from modules.embedding.active import active_index
from modules.embedding.spec import EmbedderSpec

# By the embedder's id and the tool's text.
_kept: dict[tuple[str, str], list[float]] = {}


class ToolVectors:
    def __init__(self, spec: EmbedderSpec) -> None:
        self._spec = spec

    def query(self, text: str) -> list[float]:
        return encoder.embed(self._spec, [text], encoder.Purpose.QUERY)[0]

    def documents(self, texts: list[str]) -> list[list[float]]:
        missing = [t for t in dict.fromkeys(texts) if (self._spec.id, t) not in _kept]
        if missing:
            made = encoder.embed(self._spec, missing, encoder.Purpose.DOCUMENT)
            _kept.update(
                ((self._spec.id, t), v) for t, v in zip(missing, made, strict=True)
            )
        return [_kept[(self._spec.id, t)] for t in texts]


def tool_vectors(session: Session) -> ToolVectors | None:
    """None before onboarding chooses an embedder: ranking then goes by keyword alone."""
    index = active_index(session)
    return None if index is None else ToolVectors(index.spec)
