"""What a job is called and which slots it fills, from the catalog that offered it."""

from modules.llm.catalog.local.install.plan import InstallPlan
from modules.llm.catalog.local.service import LocalCatalogService
from modules.llm.model_type import ModelType
from modules.llm.selectable import selectable_for


def describe_install(
    service: LocalCatalogService, catalog_id: str, plan: InstallPlan
) -> tuple[str, tuple[ModelType, ...]]:
    for row in service.catalog().rows:
        for build in row.builds:
            if build.catalog_id == catalog_id:
                slots = selectable_for(
                    row.classification.types, row.classification.known
                )
                return f"{row.name} {build.build.quantization}", tuple(slots)
    # A searched build: its repo names it, and search reaches only chat.
    repo = plan.build.weights.repo or plan.model_id
    return f"{repo} {plan.build.quantization}", (ModelType.TEXT_GEN,)
