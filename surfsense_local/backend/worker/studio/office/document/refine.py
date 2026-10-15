"""Refine: one model call rewrites the whole spec, which renders as the next version."""

from modules.artifacts.studio_documents.recipe import Refinement
from modules.llm import prompting
from modules.llm.providers.types import Message
from modules.llm.resolution import ResolvedGeneration
from worker.studio.office.document import markdown_path, script_path
from worker.studio.office.document.figure_list import markdown_figures, script_figures
from worker.studio.office.document.reply import markdown_reply, script_reply
from worker.studio.office.spec import Office
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, SourceImage


def refine(
    office: Office,
    model: ResolvedGeneration,
    refinement: Refinement,
    figures: tuple[SourceImage, ...],
    title: str,
) -> Built:
    """Nothing is patched or diffed: the model returns the whole revised spec."""
    base = refinement.base
    if base.kind == "markdown":
        system = prompting.load(
            __package__,
            model.tier,
            case="refine_markdown",
            label=office.label,
            figures=markdown_figures(figures),
        )
    else:
        system = prompting.load(
            __package__,
            model.tier,
            case="refine_python",
            label=office.label,
            library=office.library,
            rules=script_path.rules(office),
            figures=script_figures(figures),
        )
    raw = generate.complete(
        model,
        [
            Message(role="system", content=system),
            Message(
                role="user",
                content=request(base.kind, base.text, refinement.instruction),
            ),
        ],
    )
    if base.kind == "markdown":
        return markdown_path.build(office, markdown_reply(raw), figures, title)
    return script_path.run(office, script_reply(raw), figures, title)


def request(kind: str, text: str, instruction: str) -> str:
    """The user's turn: the current spec, fenced, then the change they asked for."""
    language = "markdown" if kind == "markdown" else "python"
    # A fence longer than any inside the spec, so a chart block cannot close it.
    fence = "`" * max(3, _longest_backtick_run(text) + 1)
    return (
        f"The current document:\n\n{fence}{language}\n{text}\n{fence}\n\n"
        f"Change it as follows: {instruction}"
    )


def _longest_backtick_run(text: str) -> int:
    longest = run = 0
    for character in text:
        run = run + 1 if character == "`" else 0
        longest = max(longest, run)
    return longest
