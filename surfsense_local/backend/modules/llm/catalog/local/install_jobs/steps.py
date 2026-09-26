"""What one install does, in the order its events say it."""

from collections.abc import AsyncIterator, Callable

from sqlalchemy.orm import Session

from modules.llm.catalog.local.install.plan import InstallPlan, InstallRefusedError
from modules.llm.catalog.local.service import LocalCatalogService
from modules.llm.model_type import ModelType
from modules.llm.schemas import SelectionRead
from modules.llm.selection import choose_model


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
    async for step in service.install(checked):
        yield {
            "type": "downloading",
            "message": step.status,
            "completed": step.completed,
            "total": step.total,
        }
    yield {"type": "verifying", "message": "Checking the model"}
    engine = service.engine(checked.engine)
    ready = "Model is ready"
    async for step in engine.after_install(checked.model_id):
        if step.kind == "complete":
            ready = step.message
            continue
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
