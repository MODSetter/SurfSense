from fastapi import Depends

from api.dependencies import SessionDep
from modules.embedding.active import require_active_index


def _require_embedder_chosen(session: SessionDep) -> None:
    """Refuse before queueing work that would be embedded with no model chosen."""
    require_active_index(session)


EMBEDDER_CHOSEN = Depends(_require_embedder_chosen)
