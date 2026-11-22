"""An image a document or page names, held to the sources the turn may use."""

from collections.abc import Iterable

from modules.agent.tool_endpoint.tool import ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.documents.source_figures import parse_figure_name


def refuse_unselected_images(scope: TurnScope, images: Iterable[str]) -> None:
    """An image is its source's content: one from a source the turn may not use is refused."""
    names = list(images)
    if not names:
        return
    selected = scope.selected()
    for name in names:
        parsed = parse_figure_name(name)
        # A name no source has is the service's to refuse, as before.
        if parsed is not None and parsed[0] not in selected:
            raise ToolCallError(
                f'Image "{name}" comes from source {parsed[0]}, which is not '
                "selected for this request. Place only images from the selected "
                "sources, or ask the user to select that one."
            )
