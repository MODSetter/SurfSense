"""OpenTelemetry GenAI semantic-convention vocabulary.

One home for the ``gen_ai.*`` keys so agent spans/metrics match the spec.
Ref: https://opentelemetry.io/docs/specs/semconv/gen-ai/
"""

from __future__ import annotations

GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"
GEN_AI_TOKEN_TYPE = "gen_ai.token.type"

# Operation value for chat completions.
GEN_AI_OPERATION_CHAT = "chat"

# Instrument name for token usage (spec-defined).
METRIC_GEN_AI_TOKEN_USAGE = "gen_ai.client.token.usage"
