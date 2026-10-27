"""Which models count as strong enough to write a document script."""

from modules.llm.capability.studio_output import studio_output
from modules.llm.models import SelectedModel


def writes_script(selection: SelectedModel) -> bool:
    """The full Studio path, decided where Settings reads it too."""
    return studio_output(selection) == "full"
