"""models.dev in the app's own words: evidence and display fields, nothing else.

models.dev is written for the Vercel AI SDK, so it names JavaScript packages,
environment variables and prices this app never reads. What survives is what
the classifier, support and the screen read, under the provider that serves
the model, because the same id means what each provider says it means.
"""

from typing import Any

__all__ = ["translate"]


def translate(api: dict[str, Any]) -> dict[str, Any]:
    """The whole models.dev listing, keyed provider then model."""
    return {
        "providers": {
            provider_id: _provider(provider) for provider_id, provider in api.items()
        }
    }


def _provider(provider: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": provider["name"],
        "doc": provider.get("doc"),
        "models": {
            model_id: _model(model)
            for model_id, model in (provider.get("models") or {}).items()
        },
    }


def _model(model: dict[str, Any]) -> dict[str, Any]:
    limit = model.get("limit") or {}
    return {
        "name": model.get("name") or model["id"],
        "family": model.get("family"),
        "description": model.get("description"),
        "release_date": model.get("release_date"),
        "status": model.get("status"),
        "modalities": model.get("modalities") or {"input": [], "output": []},
        # 0 means "not a token model" upstream, which is not a window.
        "context": _positive(limit.get("context")),
        "output_limit": _positive(limit.get("output")),
        # None is not no: an absent field stays absent rather than becoming false.
        "tool_call": model.get("tool_call"),
        "reasoning": model.get("reasoning"),
        "reasoning_options": model.get("reasoning_options"),
        "structured_output": model.get("structured_output"),
        "temperature": model.get("temperature"),
    }


def _positive(value: object) -> int | None:
    return value if isinstance(value, int) and value > 0 else None
