"""Which models count as strong enough to write a document script."""

from modules.llm.models import SelectedModel


def writes_script(selection: SelectedModel) -> bool:
    """Provisional: a remote model writes a script, one served from this computer Markdown.

    Local means llama.cpp or a connection on loopback (Ollama, LM Studio). No
    measured capability exists yet; 05's capability profile replaces this rule.
    """
    return not selection.fingerprint.local
