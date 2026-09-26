"""The voice podcasts get when none is chosen: the audio model the app ships."""

from sqlalchemy.orm import Session

from modules.llm.catalog.local.dependencies import get_local_catalog
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.providers import audiocpp
from modules.llm.selection import choose_model


async def choose_default_voice(session: Session) -> None:
    """Run at every startup, so a choice whose model was deleted falls back to
    it at the next launch. A model already chosen is left alone."""
    if session.get(SelectedModel, ModelType.AUDIO_GEN) is not None:
        return
    shipped = next(
        (m for m in get_local_catalog().audiocpp.installed() if m.bundled), None
    )
    if shipped is not None:
        await choose_model(
            session, ModelType.AUDIO_GEN, audiocpp.PROVIDER, shipped.model_id
        )
