"""Names that must be unique within their list, so the app can find each one."""

from typing import Protocol

from pydantic import AfterValidator


class _Named(Protocol):
    """Anything declared by name in a list."""

    name: str


def unique_names(kind: str) -> AfterValidator:
    """The rule for a list whose items the app finds by name."""

    # Runs once the list's items are valid: a duplicate in a list that has another
    # error shows on the next check, which keeps this to the typed items.
    def check[T: _Named](items: list[T]) -> list[T]:
        """Refuses the second item that takes a name already used."""
        seen: set[str] = set()
        for item in items:
            if item.name in seen:
                raise ValueError(f"two {kind} are named {item.name}")
            seen.add(item.name)
        return items

    return AfterValidator(check)
