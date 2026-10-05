"""Which models count as strong enough to write a document script."""

from modules.llm.models import SelectedModel
from modules.llm.providers import llamacpp


def writes_script(selection: SelectedModel) -> bool:
    """Provisional: a model on a server writes a script, one on llama.cpp writes Markdown.

    No measured capability exists yet; 05's capability profile replaces this rule.
    """
    return selection.provider != llamacpp.PROVIDER
