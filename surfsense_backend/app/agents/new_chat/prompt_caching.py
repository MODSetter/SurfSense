"""Backward-compatible shim.

The LiteLLM prompt-caching helper now lives in the shared agent kernel at
``app.agents.shared.prompt_caching``. This module re-exports it so frozen
single-agent code (``chat_deepagent``) keeps working until that stack is
retired.
"""

from __future__ import annotations

from app.agents.shared.prompt_caching import apply_litellm_prompt_caching

__all__ = ["apply_litellm_prompt_caching"]
