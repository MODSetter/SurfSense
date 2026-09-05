from modules.llm.providers.openrouter.provider import _answers_text, _delta


def test_delta_reads_the_content_of_an_openai_frame() -> None:
    """A normal frame yields its token."""
    line = 'data: {"choices": [{"delta": {"content": "hi"}}]}'
    assert _delta(line) == "hi"


def test_delta_ignores_keepalives_and_the_done_sentinel() -> None:
    """Blank lines, comments, and `[DONE]` are not tokens."""
    assert _delta("") is None
    assert _delta(": keep-alive") is None
    assert _delta("data: [DONE]") is None


def test_delta_ignores_a_frame_with_no_token() -> None:
    """Role-only openers and empty-choice frames carry no content."""
    assert _delta('data: {"choices": [{"delta": {"role": "assistant"}}]}') is None
    assert _delta('data: {"choices": []}') is None


def test_a_text_model_answers_but_an_image_model_does_not() -> None:
    """Generation needs text out; an image endpoint is filtered away."""
    assert _answers_text({"architecture": {"output_modalities": ["text"]}}) is True
    assert _answers_text({"architecture": {"output_modalities": ["image"]}}) is False


def test_a_model_without_modality_metadata_is_kept() -> None:
    """Absent metadata is no reason to hide a model the user may want."""
    assert _answers_text({}) is True
