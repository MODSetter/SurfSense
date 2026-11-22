"""How long one run of an action may last before the app stops it."""

from typing import Annotated

from pydantic import AfterValidator

# Six hours: long enough for a large import, short enough that a hung plugin ends.
_LONGEST = 21600


def _between_a_second_and_six_hours(value: int) -> int:
    """Refuses a timeout no run could meet, or one that lets a hung plugin run on."""
    if not 1 <= value <= _LONGEST:
        raise ValueError(f"must be 1 to {_LONGEST} seconds")
    return value


TimeoutSeconds = Annotated[int, AfterValidator(_between_a_second_and_six_hours)]
