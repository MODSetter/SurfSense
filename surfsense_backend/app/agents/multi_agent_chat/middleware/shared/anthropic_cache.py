"""Anthropic prompt caching annotations on system/tool/message blocks."""

from __future__ import annotations

from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware


def build_anthropic_cache_mw() -> AnthropicPromptCachingMiddleware:
    return AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore")
