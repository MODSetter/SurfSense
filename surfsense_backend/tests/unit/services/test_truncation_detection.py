"""Guard the output-truncation detector.

``langchain_litellm`` (0.6.4) drops ``finish_reason`` from streamed chunks, so
a token-limit cut reaches the UI silently. The LiteLLM success callback still
sees the real ``finish_reason`` and usage, so detection must honour both: the
gold ``finish_reason == "length"`` signal, and a usage>=max_tokens fallback for
paths where ``finish_reason`` is absent.
"""

from app.services.token_tracking_service import is_output_truncated


def test_finish_reason_length_is_truncated():
    assert is_output_truncated("length", completion_tokens=10, max_tokens=999) is True


def test_finish_reason_stop_is_not_truncated_even_at_cap():
    # An explicit non-length reason wins over the usage heuristic.
    assert is_output_truncated("stop", completion_tokens=24, max_tokens=24) is False


def test_usage_fallback_when_finish_reason_missing():
    assert is_output_truncated(None, completion_tokens=24, max_tokens=24) is True
    assert is_output_truncated("", completion_tokens=30, max_tokens=24) is True


def test_under_cap_without_finish_reason_is_not_truncated():
    assert is_output_truncated(None, completion_tokens=10, max_tokens=24) is False


def test_no_cap_configured_cannot_infer_from_usage():
    assert is_output_truncated(None, completion_tokens=9999, max_tokens=None) is False
    assert is_output_truncated(None, completion_tokens=9999, max_tokens=0) is False
