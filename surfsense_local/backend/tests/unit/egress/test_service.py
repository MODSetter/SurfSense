import pytest

from modules.egress import service as egress

pytestmark = pytest.mark.unit


def test_a_library_pull_reports_the_ollama_registry() -> None:
    """Ollama's own model library is served from its registry."""
    assert egress.ollama_pull_host("qwen3:8b") == "registry.ollama.ai"


def test_an_hf_co_fallback_pull_reports_hugging_face() -> None:
    """Ollama fetches `hf.co/<repo>` pulls straight from Hugging Face, not its own registry."""
    assert egress.ollama_pull_host("hf.co/Qwen/Qwen3-8B-GGUF:Q4_K_M") == "huggingface.co"
