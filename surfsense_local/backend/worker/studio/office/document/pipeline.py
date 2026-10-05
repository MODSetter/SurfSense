"""Studio's Word or PDF draft: the path the selected model takes."""

from modules.llm.resolution import ResolvedGeneration
from worker.studio.office.document import markdown_path, script_path
from worker.studio.office.document.strength import writes_script
from worker.studio.office.spec import Office
from worker.studio.shared.artifact import Built, Source


def render(
    office: Office,
    model: ResolvedGeneration,
    sources: list[Source],
    user_prompt: str | None,
) -> Built:
    path = script_path if writes_script(model.selection) else markdown_path
    return path.draft(office, model, sources, user_prompt)
