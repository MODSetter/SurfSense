"""Vision-capability gate for image-bearing turns.

Capability safety net for explicit (non-auto-pin) selections: a turn carrying
user-uploaded images cannot be routed to a chat config that LiteLLM's
authoritative model map *explicitly* marks as text-only (``supports_vision``
set to False). The check is intentionally narrow — it only fires when LiteLLM
is *certain* the model can't accept image input; unknown / unmapped /
vision-capable models pass through.

Without this guard a known-text-only model would 404 at the provider with
``"No endpoints found that support image input"``, surfacing as an opaque
``SERVER_ERROR`` SSE chunk; failing here lets us return a friendly message that
tells the user what to change.
"""

from __future__ import annotations

from app.agents.chat.runtime.llm_config import AgentConfig
from app.observability import otel as ot


def check_image_input_capability(
    *,
    user_image_data_urls: list[str] | None,
    agent_config: AgentConfig | None,
) -> tuple[str, str] | None:
    """Return ``(user_message, error_code)`` when the gate trips, else ``None``.

    The caller emits one terminal-error SSE frame on a non-``None`` return.
    """
    if not (user_image_data_urls and agent_config is not None):
        return None

    from app.services.provider_capabilities import is_known_text_only_chat_model

    agent_litellm_params = agent_config.litellm_params or {}
    agent_base_model = (
        agent_litellm_params.get("base_model")
        if isinstance(agent_litellm_params, dict)
        else None
    )
    if not is_known_text_only_chat_model(
        litellm_provider=agent_config.provider,
        model_name=agent_config.model_name,
        base_model=agent_base_model,
        custom_provider=agent_config.custom_provider,
    ):
        return None

    model_label = agent_config.config_name or agent_config.model_name or "model"
    ot.add_event("quota.denied", {"quota.code": "MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT"})
    return (
        (
            f"The selected model ({model_label}) does not support "
            "image input. Switch to a vision-capable model "
            "(e.g. GPT-4o, Claude, Gemini) or remove the image "
            "attachment and try again."
        ),
        "MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT",
    )
