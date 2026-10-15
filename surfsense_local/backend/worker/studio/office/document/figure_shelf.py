"""The figures the selected sources hold, as a draft or a refine may place them."""

from collections.abc import Iterable
from dataclasses import replace

from sqlalchemy.orm import Session

from modules.documents.source_figures import FiguresPending, figure_file, list_figures
from worker.studio.shared.artifact import Source, SourceImage


def with_figures(
    session: Session, workspace_id: int, sources: list[Source]
) -> list[Source]:
    return [
        replace(source, figures=figures_of(session, workspace_id, [source.document_id]))
        for source in sources
    ]


def figures_of(
    session: Session, workspace_id: int, document_ids: Iterable[int]
) -> tuple[SourceImage, ...]:
    """Every figure on disk; a source still being read offers none this time.

    Asking queues the figures pass for a source ingested before figures were
    kept, so the next draft from it can place them.
    """
    found: list[SourceImage] = []
    for document_id in document_ids:
        try:
            listed = list_figures(session, workspace_id, document_id)
        except (FiguresPending, LookupError):
            continue
        for figure in listed:
            try:
                path = figure_file(session, workspace_id, figure.name)
            except LookupError:
                continue
            found.append(SourceImage(figure.name, figure.caption, path))
    return tuple(found)


def by_name(figures: Iterable[SourceImage]) -> dict[str, SourceImage]:
    return {figure.name: figure for figure in figures}


def shelf_of(sources: list[Source]) -> tuple[SourceImage, ...]:
    return tuple(figure for source in sources for figure in source.figures)
