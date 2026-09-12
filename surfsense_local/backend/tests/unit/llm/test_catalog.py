import pytest

from modules.llm.providers.ollama.provider import OllamaProvider

pytestmark = pytest.mark.unit


def test_the_catalog_is_the_curated_qwen_family() -> None:
    """Ollama lists no library, so what it offers is exactly what is curated."""
    names = [entry.name for entry in OllamaProvider("http://unused").catalog()]

    assert names
    assert all(name.startswith("qwen") for name in names)
