"""This build's release version, as `scripts/bump-version.sh` writes it into pyproject.toml."""

from functools import lru_cache
from importlib.metadata import version

# A frozen build carries the package's metadata only because bundling/api_inputs.py copies it.
PACKAGE = "surfsense-local-backend"


@lru_cache
def app_version() -> str:
    return version(PACKAGE)
