"""Found models as the screen's rows: priced like any other, used with no download.

Pure, like the rest of the catalog's rows: the finding, the machine and the
install ids in, rows out. A file already used in place leads as installed under
the name the runtime knows it by; any other carries the id that uses it.
"""

from collections.abc import Callable, Mapping, Set

from modules.llm.catalog.local.build import Build, BuildFile, FileRole
from modules.llm.catalog.local.classifier import classify
from modules.llm.catalog.local.engines.llamacpp import ENGINE
from modules.llm.catalog.local.engines.llamacpp.elsewhere.find import FoundModel
from modules.llm.catalog.local.engines.llamacpp.elsewhere.in_place import found_in
from modules.llm.catalog.local.engines.llamacpp.pricing import price
from modules.llm.catalog.local.engines.llamacpp.support import template_support
from modules.llm.catalog.local.rows import (
    BuildRow,
    Lead,
    LeadReason,
    LocalRow,
    LocalSupport,
    Origin,
)
from modules.llm.fit import HardwareBudget, badge


def elsewhere_row(
    found: FoundModel,
    budget: HardwareBudget,
    catalog_id: str,
    *,
    used_as: str | None = None,
    selected: Set[str] = frozenset(),
) -> LocalRow:
    """`used_as` is the runtime's name for it once used in place; `catalog_id`
    uses it, and is empty once it is."""
    reads = found.projector is not None
    fit = price(found.shape, found.weights_bytes, found.projector_bytes, budget)
    files = (BuildFile(FileRole.WEIGHTS, found.path.name, found.weights_bytes),)
    if found.projector is not None:
        files += (
            BuildFile(
                FileRole.PROJECTOR,
                found.projector.name,
                found.projector_bytes,
                gguf=dict(found.projector_kv),
            ),
        )
    tools, reasoning = template_support(found.template)
    label = found.label
    if used_as is not None and used_as in selected:
        why = LeadReason.IN_USE
    elif used_as is not None:
        why = LeadReason.INSTALLED
    else:
        why = LeadReason.DEFAULT
    return LocalRow(
        id=used_as or catalog_id,
        origin=Origin.ELSEWHERE,
        name=label.name,
        family="",
        classification=classify(label.architecture),
        support=LocalSupport(
            context=label.context,
            reads_images=reads,
            tools=tools,
            reasoning=reasoning,
        ),
        builds=(
            BuildRow(
                catalog_id="" if used_as else catalog_id,
                build=Build(label.quantization, files),
                fit=fit,
                badge=badge(fit, budget),
                installed_as=used_as,
                recommended=False,
                reads_images=reads,
                projector_checked=True,
            ),
        ),
        default_quantization=None,
        recommended=False,
        engine=ENGINE,
        lead=Lead(label.quantization, why),
        found_in=found_in(found),
    )


def elsewhere_rows(
    found: tuple[FoundModel, ...],
    budget: HardwareBudget,
    mint: Callable[[FoundModel], str],
    used: Mapping[str, str],
    *,
    selected: Set[str] = frozenset(),
) -> tuple[LocalRow, ...]:
    """`used` maps each file used in place to the runtime's name for it."""
    rows = []
    for model in found:
        used_as = used.get(str(model.path))
        rows.append(
            elsewhere_row(
                model,
                budget,
                "" if used_as else mint(model),
                used_as=used_as,
                selected=selected,
            )
        )
    return tuple(rows)
