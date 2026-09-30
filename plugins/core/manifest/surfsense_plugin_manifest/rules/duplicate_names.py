"""Names that must be unique within their list, so the app can find each one."""

from typing import Protocol

from pydantic import AfterValidator


class _Named(Protocol):
    name: str


def unique_names(kind: str) -> AfterValidator:
    # Runs once the list's items are valid: a duplicate in a list that has another
    # error shows on the next check, which keeps this to the typed items.
    def check[T: _Named](items: list[T]) -> list[T]:
        seen: set[str] = set()
        for item in items:
            if item.name in seen:
                raise ValueError(f"two {kind} are named {item.name}")
            seen.add(item.name)
        return items

    return AfterValidator(check)
