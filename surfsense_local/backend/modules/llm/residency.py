"""Holding the chosen local model in memory before anyone asks it anything.

The router loads on demand, which means the load lands on whoever asks the
first question: tens of seconds of nothing, at the one moment someone is
watching. This moves it to the moments the app already knows a model is about
to be wanted and nobody is waiting yet — choosing one, and starting up.

Gated on the selection's provider rather than on whether a runtime is running.
Someone answering through their own endpoint runs no local model, and must not
be made to hold one in memory for a runtime they never use.
"""

import logging

import httpx

from modules.llm.admission.local_runtime import LocalAdmission
from modules.llm.models import SelectedModel
from modules.llm.providers.llamacpp import PROVIDER, RouterClient
from modules.llm.providers.llamacpp.unload import unload_text_models

logger = logging.getLogger(__name__)


async def release_unselected(
    selected: SelectedModel | None,
    base_url: str,
    admission: LocalAdmission,
    *,
    transport: httpx.BaseTransport | None = None,
) -> list[str]:
    """Unload the local chat model once chat has moved to another provider.

    A loaded model otherwise stays until the app quits: 1.5 GB of RAM and 6 GB
    of graphics memory for a 1.7B, all of it page-file backed on Windows. Waits
    for what is generating locally to finish, as an image's hold does; the next
    local request loads a model again. Never raises.
    """
    if selected is not None and selected.provider == PROVIDER:
        return []
    try:
        async with admission.given_up():
            return await unload_text_models(RouterClient(base_url, transport=transport))
    except (httpx.HTTPError, OSError) as error:
        logger.info("could not unload the local chat model: %s", error)
        return []


async def warm_selected(
    selected: SelectedModel | None,
    base_url: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> bool:
    """Load `selected` if it is a local chat model. True when it was loaded.

    Never raises. The sidecar restarts whenever the preset is rewritten, so a
    warm landing in that window is routine rather than exceptional, and what it
    costs is the wait it was trying to avoid: exactly where the caller already
    was.

    Blocks until the model is resident, because that is what `POST /models/load`
    does. Every caller runs this off the path of a response for that reason.
    """
    if selected is None or selected.provider != PROVIDER:
        return False

    try:
        await RouterClient(base_url, transport=transport).load(selected.name)
    except (httpx.HTTPError, OSError) as error:
        logger.info("could not warm %s: %s", selected.name, error)
        return False
    return True
