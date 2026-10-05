"""A small model's path: it writes Markdown in one call, and a builder renders it."""

import re
from collections.abc import Iterable

from modules.artifacts.script_documents.spec import DocumentSpec
from modules.llm import prompting
from modules.llm.resolution import ResolvedGeneration
from worker.studio.office.document.figure_list import markdown_figures
from worker.studio.office.document.figure_shelf import by_name, shelf_of
from worker.studio.office.document.reply import first_heading, markdown_reply
from worker.studio.office.markdown import markdown_to_pdf, markdown_to_word
from worker.studio.office.spec import Office
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source, SourceImage, fallback_title
from worker.studio.shared.text import file_stem

_FIGURE_REFERENCE = re.compile(r"\(\s*<?image:([0-9]+-[0-9]+)")


def draft(
    office: Office,
    model: ResolvedGeneration,
    sources: list[Source],
    user_prompt: str | None,
) -> Built:
    figures = shelf_of(sources)
    system = prompting.load(
        __package__,
        model.tier,
        case="markdown",
        label=office.label,
        focus=prompting.focus(user_prompt),
        figures=markdown_figures(figures),
    )
    raw = generate.run_model(model, system, sources)
    return build(
        office,
        markdown_reply(raw),
        figures,
        fallback_title(user_prompt, sources, office.label),
    )


def build(
    office: Office, markdown: str, figures: Iterable[SourceImage], title: str
) -> Built:
    """The file the Markdown describes, with the Markdown kept as its spec and body."""
    if not markdown:
        raise ValueError("the model returned an empty document")
    paths = {name: figure.path for name, figure in by_name(figures).items()}
    render = markdown_to_word if office.key == "docx" else markdown_to_pdf
    data = render(markdown, paths)
    placed = tuple(
        dict.fromkeys(
            name for name in _FIGURE_REFERENCE.findall(markdown) if name in paths
        )
    )
    title = first_heading(markdown) or title
    return Built(
        title=title,
        markdown=markdown,
        primary=data,
        primary_mime=office.mime,
        primary_filename=f"{file_stem(title, office.stem)}.{office.ext}",
        spec=DocumentSpec("markdown", markdown, office.key, placed).as_metadata(),
    )
