"""Pages Docling reads in one conversion: a run of a PDF's pages, cut into batches."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# A scan reads at about 3 s a page, so a batch takes some 25 s: the most the
# queue waits once a long reading should give way.
BATCH_PAGES = 8


@dataclass(frozen=True)
class PageRun:
    """Pages first to last, counted from 1, both included."""

    first: int
    last: int

    @property
    def pages(self) -> range:
        return range(self.first, self.last + 1)


def runs_of(pages: Iterable[int]) -> list[PageRun]:
    """Ascending page numbers as runs of consecutive pages."""
    runs: list[PageRun] = []
    for page in pages:
        if runs and page == runs[-1].last + 1:
            runs[-1] = PageRun(runs[-1].first, page)
        else:
            runs.append(PageRun(page, page))
    return runs


def batches_of(run: PageRun, size: int | None = None) -> list[PageRun]:
    """The run in batches of `size` pages, BATCH_PAGES unless given, the last
    one shorter."""
    size = size or BATCH_PAGES
    return [
        PageRun(first, min(first + size - 1, run.last))
        for first in range(run.first, run.last + 1, size)
    ]


def described(runs: Sequence[PageRun]) -> str:
    """As a reader writes them: "1, 4-6"."""
    return ", ".join(
        str(run.first) if run.first == run.last else f"{run.first}-{run.last}"
        for run in runs
    )
