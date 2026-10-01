"""What the chosen local image model's server is doing, for the screen to say.

Asked, never started: sd-server holds one model, and Studio pays for loading it
only when a job needs one.
"""

import httpx
from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.llm.catalog.local.service import LocalCatalogService
from modules.llm.image_server_state import ImageServerState
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.providers.sdcpp import provider as sdcpp
from modules.llm.providers.sdcpp.serving import serves

# A probe of a loopback server either answers at once or is not there.
PROBE_TIMEOUT = httpx.Timeout(2.0)


def _chosen_weights(
    session: Session, service: LocalCatalogService, model_type: ModelType
) -> ImageServerState | str:
    selected = session.get(SelectedModel, model_type)
    if selected is None or selected.provider != sdcpp.PROVIDER:
        return ImageServerState.NONE
    image = service.sdcpp.installed_image(selected.name)
    return ImageServerState.MISSING if image is None else image.served_file


async def local_image_state(
    session: Session, service: LocalCatalogService, model_type: ModelType
) -> ImageServerState:
    chosen = await transact(session, _chosen_weights, service, model_type)
    if isinstance(chosen, ImageServerState):
        return chosen
    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as client:
        running = await serves(client, sdcpp.root_url(), chosen)
    return ImageServerState.RUNNING if running else ImageServerState.IDLE
