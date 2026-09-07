from worker.studio.builders.summary import summary
from worker.studio.builders.types import Builder, Built, Source

# format key -> builder. Adding a format is a module and one line here; the
# API's dependency-free catalog (modules/artifacts/formats.py) must list the
# same keys, which tests/unit/worker/test_studio_builders.py asserts.
BUILDERS: dict[str, Builder] = {builder.key: builder for builder in (summary,)}

__all__ = ["BUILDERS", "Builder", "Built", "Source"]
