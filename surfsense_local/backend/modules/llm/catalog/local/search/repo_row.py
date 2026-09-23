"""A searched repo as a local row, from its listing alone.

The same row shape curated and downloaded models use, so the screen and every
reader of a build never ask where it came from. What only a header can settle is
marked so: the fit is an estimate, the type approximate, and a projector found
by name is not yet checked. Search describes and never recommends: no default,
no recommended build, no star.
"""

import dataclasses
from collections.abc import Callable

from modules.llm.catalog.local.builds import Build, builds_in
from modules.llm.catalog.local.classifier import classify
from modules.llm.catalog.local.pricing import estimated_price
from modules.llm.catalog.local.rows import BuildRow, LocalRow, Origin
from modules.llm.catalog.local.search.listing import RepoListing
from modules.llm.catalog.local.support import LocalSupport
from modules.llm.fit import HardwareBudget, badge
from modules.llm.model_type import ModelType


def repo_row(
    listing: RepoListing, budget: HardwareBudget, mint: Callable[[Build], str]
) -> LocalRow:
    classification = dataclasses.replace(
        classify(listing.architecture_hint, listing.pipeline_tag), approximate=True
    )
    chats = ModelType.TEXT_GEN in classification.types
    rows = []
    for build in builds_in(listing.files, repo=listing.repo, revision=listing.revision):
        projector_bytes = build.projector.size_bytes if build.projector else 0
        fit = estimated_price(build.weights_bytes, projector_bytes, budget)
        rows.append(
            BuildRow(
                catalog_id=mint(build) if chats else "",
                build=build,
                fit=fit,
                badge=badge(fit, budget),
                installed_as=None,
                recommended=False,
                reads_images=build.projector is not None,
                projector_checked=False,
            )
        )
    return LocalRow(
        id=listing.repo,
        origin=Origin.SEARCH,
        name=listing.repo,
        family="",
        classification=classification,
        support=LocalSupport(
            context=None,
            reads_images=any(r.reads_images for r in rows),
            tools=None,
            reasoning=None,
        ),
        builds=tuple(rows),
        default_quantization=None,
        recommended=False,
    )
