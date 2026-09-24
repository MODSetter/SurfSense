"""Which builds are pinned and which a row downloads: Q4_0, the build sd-server was
measured on here. With no fit estimate, nothing steps to another.
"""

from collections.abc import Sequence

from modules.llm.catalog.local.build import Build

PREFERENCE = ("Q4_0",)


def default_build(builds: Sequence[Build]) -> Build | None:
    """The first build in the preference order, or None."""
    for label in PREFERENCE:
        for build in builds:
            if build.quantization == label:
                return build
    return None
