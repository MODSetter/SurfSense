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

from modules.llm.models import SelectedModel
from modules.llm.providers.llamacpp import PROVIDER, RouterClient

logger = logging.getLogger(__name__)


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
