from modules.llm.providers.llamacpp.router_client import RouterClient


async def unload_text_models(router: RouterClient) -> list[str]:
    """Unload every model the runtime holds, so the graphics card is free.

    The router loads one again on the next request that names it.
    """
    unloaded = []
    for resident in await router.models():
        if resident.loaded:
            await router.unload(resident.id)
            unloaded.append(resident.id)
    return unloaded
