"""Vision LLM resolution + auto-pick logic for the harness's ``setup`` command.

Two responsibilities:

1. Resolve an explicit ``--vision-llm <slug>`` to a global OpenRouter
   vision-capable model id that ``set_model_roles(vision_model_id=...)`` can
   accept.
2. Auto-pick the strongest registered vision config when the operator
   doesn't pass ``--vision-llm`` but the scenario / benchmark needs one.

The priority list mirrors the recommended slugs in the README so the
auto-pick is deterministic and reviewable.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .clients.search_space import VisionLlmConfigEntry

# Order matters — first match wins when auto-picking. Keep these in sync
# with the "Recommended vision slugs" table in the README so the
# auto-pick story is the same one users read about.
RECOMMENDED_VISION_PRIORITY: tuple[str, ...] = (
    "anthropic/claude-sonnet-4.5",
    "anthropic/claude-opus-4.7",
    "openai/gpt-5",
    "google/gemini-2.5-pro",
)


class VisionConfigError(RuntimeError):
    """Raised when no vision config can be resolved (explicit or auto)."""


@dataclass(frozen=True)
class ResolvedVisionConfig:
    """Result of ``resolve_vision_llm`` — what to attach + a label for logs."""

    config_id: int
    provider_model: str
    selected_via: str  # "explicit" | "auto-priority" | "auto-fallback"


def _openrouter_only(entries: Iterable[VisionLlmConfigEntry]) -> list[VisionLlmConfigEntry]:
    return [e for e in entries if e.provider == "OPENROUTER" and not e.is_auto_mode]


def resolve_vision_llm(
    candidates: list[VisionLlmConfigEntry],
    *,
    explicit_slug: str | None,
) -> ResolvedVisionConfig:
    """Resolve a vision LLM config id from a slug or by auto-picking.

    * If ``explicit_slug`` is given: must match exactly one OpenRouter
      vision config's ``model_name``. Raises ``VisionConfigError`` with a
      friendly listing if zero / many match.
    * Otherwise: walk ``RECOMMENDED_VISION_PRIORITY`` in order and return
      the first registered one. If none of the recommended slugs are
      registered, fall back to the first OpenRouter vision config in the
      list (deterministic by listing order). Raises ``VisionConfigError``
      if zero are registered at all.
    """

    or_vision = _openrouter_only(candidates)

    if explicit_slug is not None:
        matches = [e for e in or_vision if e.model_name == explicit_slug]
        if not matches:
            sample = ", ".join(e.model_name for e in or_vision[:8]) or "<none>"
            raise VisionConfigError(
                f"No OpenRouter vision config found for slug '{explicit_slug}'. "
                "Make sure `openrouter_integration.vision_enabled: true` in "
                "global_llm_config.yaml and that the Celery worker has finished "
                "its first refresh. "
                f"Available OpenRouter vision slugs (sample): {sample}."
            )
        if len(matches) > 1:
            listing = "\n".join(f"  id={e.id}  name={e.name!r}" for e in matches)
            raise VisionConfigError(
                f"Multiple OpenRouter vision configs match '{explicit_slug}':\n{listing}"
            )
        only = matches[0]
        return ResolvedVisionConfig(
            config_id=only.id,
            provider_model=only.model_name,
            selected_via="explicit",
        )

    if not or_vision:
        raise VisionConfigError(
            "No OpenRouter vision LLM configs are registered with this "
            "SurfSense backend. Either pass `--no-vision-llm` to the ingest "
            "step (text-only ingestion), or enable "
            "`openrouter_integration.vision_enabled: true` in "
            "global_llm_config.yaml so the Celery worker syncs vision-capable "
            "OpenRouter models on next refresh."
        )

    by_slug = {e.model_name: e for e in or_vision}
    for preferred in RECOMMENDED_VISION_PRIORITY:
        match = by_slug.get(preferred)
        if match is not None:
            return ResolvedVisionConfig(
                config_id=match.id,
                provider_model=match.model_name,
                selected_via="auto-priority",
            )

    # Fallback: first registered OpenRouter vision config. Deterministic
    # because the backend returns them in a stable order.
    fallback = or_vision[0]
    return ResolvedVisionConfig(
        config_id=fallback.id,
        provider_model=fallback.model_name,
        selected_via="auto-fallback",
    )


__all__ = [
    "RECOMMENDED_VISION_PRIORITY",
    "ResolvedVisionConfig",
    "VisionConfigError",
    "resolve_vision_llm",
]
