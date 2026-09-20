"""What a searched model has to satisfy before it can be installed.

Eligibility is not fit: a model can be FITS and still gated, and the two must
never render as the same thing.
"""

import pytest

from modules.llm.catalog.search import TicketStore, is_supported

pytestmark = pytest.mark.unit


def test_a_supported_architecture_passes() -> None:
    """The 152 name list, matched without caring about case."""
    assert is_supported("qwen3")
    assert is_supported("GEMMA3")


def test_an_architecture_llama_cpp_cannot_run_is_refused() -> None:
    """No amount of memory helps, so this blocks rather than badges."""
    assert not is_supported("whisper")
    assert not is_supported("something-invented")


def test_a_ticket_resolves_to_the_build_the_server_priced() -> None:
    """The renderer never names a repo or a file, so the server has to."""
    store = TicketStore()

    token = store.mint("unsloth/Qwen3-8B-GGUF", "Qwen3-8B-Q4_K_M.gguf", "Q4_K_M", 5_000, now=0.0)
    ticket = store.resolve(token, now=1.0)

    assert ticket is not None
    assert ticket.repo == "unsloth/Qwen3-8B-GGUF"
    assert ticket.file == "Qwen3-8B-Q4_K_M.gguf"


def test_a_ticket_older_than_the_search_cache_is_gone() -> None:
    """A ticket outliving its row would install something the user stopped
    looking at. The route reports this as the existing stale id failure."""
    store = TicketStore(ttl_seconds=300)
    token = store.mint("r", "f.gguf", "Q4_K_M", 1, now=0.0)

    assert store.resolve(token, now=301.0) is None


def test_an_unknown_id_is_simply_absent() -> None:
    """Nothing was minted, so nothing resolves. Same answer as expiry."""
    assert TicketStore().resolve("never-minted") is None
