"""Provider-specific style hints from ``markdown/providers/`` (main agent only)."""

from __future__ import annotations

import re

from .load_md import read_prompt_md

ProviderVariant = str

_OPENAI_CODEX_RE = re.compile(
    r"\b(gpt-codex|codex-mini|gpt-[\d.]+-codex)\b", re.IGNORECASE
)
_OPENAI_REASONING_RE = re.compile(r"\b(gpt-5|o\d|o-)", re.IGNORECASE)
_OPENAI_CLASSIC_RE = re.compile(r"\bgpt-4", re.IGNORECASE)
_ANTHROPIC_RE = re.compile(r"\bclaude\b", re.IGNORECASE)
_GOOGLE_RE = re.compile(r"\bgemini\b", re.IGNORECASE)
_KIMI_RE = re.compile(r"\b(kimi[-\d.]*|moonshot)\b", re.IGNORECASE)
_GROK_RE = re.compile(r"\bgrok\b", re.IGNORECASE)
_DEEPSEEK_RE = re.compile(r"\bdeepseek\b", re.IGNORECASE)


def detect_provider_variant(model_name: str | None) -> ProviderVariant:
    if not model_name:
        return "default"
    name = model_name.strip()
    if _OPENAI_CODEX_RE.search(name):
        return "openai_codex"
    if _OPENAI_REASONING_RE.search(name):
        return "openai_reasoning"
    if _OPENAI_CLASSIC_RE.search(name):
        return "openai_classic"
    if _ANTHROPIC_RE.search(name):
        return "anthropic"
    if _GOOGLE_RE.search(name):
        return "google"
    if _KIMI_RE.search(name):
        return "kimi"
    if _GROK_RE.search(name):
        return "grok"
    if _DEEPSEEK_RE.search(name):
        return "deepseek"
    return "default"


def build_provider_hint_block(provider_variant: ProviderVariant) -> str:
    if not provider_variant or provider_variant == "default":
        return ""
    text = read_prompt_md(f"providers/{provider_variant}.md")
    return f"\n{text}\n" if text else ""
