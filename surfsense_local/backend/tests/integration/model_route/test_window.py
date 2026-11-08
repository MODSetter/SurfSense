"""The window route: what a worker sizes a prompt from, read through the API."""

import pytest

from tests.integration.model_route.conftest import LOCAL_MODEL, App, Runtime
from tests.integration.model_route.test_generate import frames, local_request

pytestmark = pytest.mark.integration

ROUTE = "/internal/models/text/window"
LOCAL = {"model": {"provider": "llamacpp", "name": LOCAL_MODEL, "connection_id": None}}


async def test_a_local_models_window_is_the_one_llama_server_loaded_it_with(
    api: App, runtime: Runtime
) -> None:
    """What the fitter allocated, read from the runtime, not what was asked for."""
    runtime.window = 8_192

    reply = await api.client.post(ROUTE, json=LOCAL)

    assert reply.status_code == 200
    assert reply.json() == {"window": 8_192}


async def test_under_an_images_hold_the_window_is_read_without_loading_the_model(
    api: App, runtime: Runtime
) -> None:
    """Reading it loads a model that is not resident, which nothing may do under
    an image's hold (ADR 0048); the window llama-server last reported answers."""
    runtime.window = 8_192
    # Admission reads the window as it seats a request.
    await frames(api.client, local_request())

    async with api.app.state.local_admission.given_up():
        reads = runtime.props_reads
        reply = await api.client.post(ROUTE, json=LOCAL)

    assert reply.status_code == 200
    assert reply.json() == {"window": 8_192}
    assert runtime.props_reads == reads
