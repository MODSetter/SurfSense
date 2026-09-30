"""Names the app, the catalog and the registry use to find things."""

import re
from typing import Annotated

from pydantic import AfterValidator

_HYPHENATED = re.compile(r"[a-z][a-z0-9-]{0,63}")


def _hyphenated(value: str) -> str:
    if not _HYPHENATED.fullmatch(value):
        raise ValueError(
            "must be lowercase letters, digits and hyphens, start with a letter,"
            " and be at most 64 characters"
        )
    return value


PluginId = Annotated[str, AfterValidator(_hyphenated)]
EntryName = Annotated[str, AfterValidator(_hyphenated)]

# Also a legal environment variable once upper-cased: SURFSENSE_PLUGIN_SECRET_<NAME>.
_VARIABLE_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}")


def _variable_name(value: str) -> str:
    if not _VARIABLE_NAME.fullmatch(value):
        raise ValueError(
            "must be lowercase letters, digits and underscores, start with a letter,"
            " and be at most 64 characters"
        )
    return value


VariableName = Annotated[str, AfterValidator(_variable_name)]
