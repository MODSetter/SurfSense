"""What one install does, in the order its events say it."""

import logging
from collections.abc import AsyncIterator, Callable

import httpx
from sqlalchemy.orm import Session

from modules.llm.catalog.local.install.plan import InstallPlan, InstallRefusedError
from modules.llm.catalog.local.service import LocalCatalogService
from modules.llm.model_type import ModelType
from modules.llm.providers.llamacpp.download import ChecksumMismatchError
from modules.llm.schemas import SelectionRead
from modules.llm.selection import choose_model

logger = logging.getLogger(__name__)

# What a pinned file answers once its repo is deleted, gated or made private.
GONE_STATUSES = frozenset({403, 404})

FILE_GONE = {
    "type": "error",
    "message": "This model is no longer available where SurfSense expects it.",
}
CHECKSUM_MISMATCH = {
    "type": "error",
    "message": "The downloaded file did not match the expected one. Retry the download.",
}


async def install_steps(
    service: LocalCatalogService,
    plan: InstallPlan,
    *,
    select: bool,
    model_type: ModelType | None,
    session_factory: Callable[[], Session],
) -> AsyncIterator[dict]:
    """Run inside the install lock; the job reports the first `starting`."""
    try:
        checked = await service.check(plan)
    except InstallRefusedError as refused:
        yield {"type": "error", "message": str(refused)}
        return
    yield {"type": "starting", "message": "Preparing download"}
    try:
        async for step in service.install(checked):
            yield {
                "type": "downloading",
                "message": step.status,
                "completed": step.completed,
                "total": step.total,
            }
    except httpx.HTTPStatusError as error:
        if error.response.status_code not in GONE_STATUSES:
            raise
        # A retry cannot help: the manifest needs this file re-pinned.
        logger.error(
            "pinned file is gone (HTTP %s): %s",
            error.response.status_code,
            error.request.url,
        )
        yield FILE_GONE
        return
    except ChecksumMismatchError as mismatch:
        # A retry may help if it keeps happening, something rewrites the file.
        logger.warning(
            "checksum mismatch, expected %s, got %s: %s",
            mismatch.expected,
            mismatch.actual,
            mismatch.url,
        )
        yield CHECKSUM_MISMATCH
        return
    yield {"type": "verifying", "message": "Checking the model"}
    engine = service.engine(checked.engine)
    ready = "Model is ready"
    async for step in engine.after_install(checked.model_id):
        if step.kind == "complete":
            ready = step.message
            continue
        # The model is on disk and the engine refused it: say why, and stop.
        if step.kind == "error":
            yield {"type": "error", "message": step.message}
            return
        yield {"type": step.kind, "message": step.message, "progress": step.progress}
    selection = None
    if select:
        yield {"type": "selecting", "message": "Selecting model"}
        with session_factory() as session:
            chosen = await choose_model(
                session,
                model_type or engine.model_types[0],
                engine.provider,
                checked.model_id,
            )
            selection = SelectionRead.model_validate(chosen).model_dump(mode="json")
    yield {"type": "complete", "message": ready, "selection": selection}
