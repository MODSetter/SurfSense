"""Which build a row downloads: the first the entry pins, since the refresh
writes them in the reviewed order. With no fit estimate, nothing steps to another.
"""

from collections.abc import Sequence

from modules.llm.catalog.local.build import Build


def default_build(builds: Sequence[Build]) -> Build | None:
    return builds[0] if builds else None
