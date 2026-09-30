"""A source's headers, found however a name is written, as HTTP defines them."""

from collections.abc import Iterable, Iterator, Mapping


class Headers(Mapping[str, str]):
    """Read-only, and found whatever case the source wrote each name in."""

    def __init__(self, pairs: Iterable[tuple[str, str]]) -> None:
        self._values = {name.lower(): value for name, value in pairs}

    def __getitem__(self, name: str) -> str:
        return self._values[name.lower()]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)
