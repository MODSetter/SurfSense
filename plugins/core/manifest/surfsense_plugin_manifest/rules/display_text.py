"""Text the app and the directory site show, bounded so a list stays readable."""

from typing import Annotated

from pydantic import AfterValidator


def _between_1_and(most: int) -> AfterValidator:
    def check(value: str) -> str:
        if not 1 <= len(value) <= most:
            raise ValueError(f"must be 1 to {most} characters")
        return value

    return AfterValidator(check)


DisplayName = Annotated[str, _between_1_and(80)]
Description = Annotated[str, _between_1_and(200)]
