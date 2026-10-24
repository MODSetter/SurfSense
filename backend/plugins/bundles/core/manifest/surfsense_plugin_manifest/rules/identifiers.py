"""The shape of each name the app finds things by; uniqueness is in duplicate_names.

Ids and action names take "-": they appear in file names and URLs.
Input and secret names take "_": they become Python arguments and variable names.
"""

import re
from typing import Annotated

from pydantic import AfterValidator


def _name_rule(separator: str, so_that: str) -> AfterValidator:
    """A name rule whose message says why the name takes these characters."""
    pattern = re.compile(rf"[a-z][a-z0-9{separator}]{{0,63}}")

    def check(value: str) -> str:
        """Refuses a name outside the rule, saying what the name is for."""
        if not pattern.fullmatch(value):
            raise ValueError(
                f'must be lowercase letters, digits and "{separator}", start with a'
                f" letter, and be at most 64 characters, so {so_that}"
            )
        return value

    return AfterValidator(check)


_safe_in_urls = _name_rule("-", "it is safe in file names and URLs")
_valid_variable = _name_rule(
    "_", "it is a valid Python argument and environment variable name"
)

PluginId = Annotated[str, _safe_in_urls]
ActionName = Annotated[str, _safe_in_urls]
VariableName = Annotated[str, _valid_variable]
