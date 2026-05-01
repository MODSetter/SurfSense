"""Pure-function quality scoring for Auto (Fastest) model selection.

This module is import-free of any service / request-path dependencies. All
numbers are computed once during the OpenRouter refresh tick (or YAML load)
and cached on the cfg dict, so the chat hot path only does a precomputed
sort and a SHA256 pick.

Score components (0-100 scale, higher is better):

* ``static_score_or``    – derived from the bulk ``/api/v1/models`` payload
  (provider prestige + ``created`` recency + pricing band + context window
  + capabilities + narrow tiny/legacy slug penalty).
* ``static_score_yaml``  – same shape for hand-curated YAML configs, plus
  an operator-trust bonus (the operator deliberately picked this model).
* ``aggregate_health``   – run on per-model ``/api/v1/models/{id}/endpoints``
  responses; returns ``(gated, score_or_none)``.

The blended ``quality_score`` (0.5 * static + 0.5 * health) is computed in
:mod:`app.services.openrouter_integration_service` because that's the only
caller that sees both halves.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Tunables (constants, not flags)
# ---------------------------------------------------------------------------

# Top-K size for deterministic spread inside the locked tier.
_QUALITY_TOP_K: int = 5

# Hard health gate: any cfg whose best non-null uptime is below this %
# is excluded from Auto-mode selection entirely.
_HEALTH_GATE_UPTIME_PCT: float = 90.0

# Health/static blend weight when a cfg has fresh /endpoints data.
_HEALTH_BLEND_WEIGHT: float = 0.5

# Static bonus applied to YAML cfgs because the operator hand-picked them.
_OPERATOR_TRUST_BONUS: int = 20

# /endpoints fan-out is bounded per refresh tick.
_HEALTH_ENRICH_TOP_N_PREMIUM: int = 50
_HEALTH_ENRICH_TOP_N_FREE: int = 30
_HEALTH_ENRICH_CONCURRENCY: int = 15
_HEALTH_FETCH_TIMEOUT_SEC: float = 5.0

# If at least this fraction of /endpoints fetches fail in a refresh cycle,
# fall back to the previous cycle's last-good cache instead of writing
# partial / stale health values.
_HEALTH_FAIL_RATIO_FALLBACK: float = 0.25

# Narrow tiny/legacy slug penalties only. We deliberately do NOT penalise
# ``-nano`` / ``-mini`` / ``-lite`` because modern frontier models ship with
# those naming patterns (``gpt-5-mini``, ``gemini-2.5-flash-lite`` etc.) and
# blanket-penalising them suppresses high-quality picks.
_TINY_LEGACY_PENALTY_PATTERNS: tuple[str, ...] = (
    "-1b-",
    "-1.2b-",
    "-1.5b-",
    "-2b-",
    "-3b-",
    "gemma-3n",
    "lfm-",
    "-base",
    "-distill",
    ":nitro",
    "-preview",
)


# ---------------------------------------------------------------------------
# Provider prestige tables
# ---------------------------------------------------------------------------

# OpenRouter-side provider slug (the prefix before ``/`` in the model id).
# Tiers are coarse: frontier labs > strong open / fast-moving labs >
# specialist labs > everything else.
PROVIDER_PRESTIGE_OR: dict[str, int] = {
    # Frontier labs
    "openai": 50,
    "anthropic": 50,
    "google": 50,
    "x-ai": 50,
    # Strong open / fast-moving labs
    "deepseek": 38,
    "qwen": 38,
    "meta-llama": 38,
    "mistralai": 38,
    "cohere": 38,
    "nvidia": 38,
    "alibaba": 38,
    # Specialist / regional / strong second-tier
    "microsoft": 28,
    "01-ai": 28,
    "minimax": 28,
    "moonshot": 28,
    "z-ai": 28,
    "nousresearch": 28,
    "ai21": 28,
    "perplexity": 28,
    # Smaller / niche providers
    "liquid": 18,
    "cognitivecomputations": 18,
    "venice": 18,
    "inflection": 18,
}

# YAML provider field (the upstream API shape the operator selected).
PROVIDER_PRESTIGE_YAML: dict[str, int] = {
    "AZURE_OPENAI": 50,
    "OPENAI": 50,
    "ANTHROPIC": 50,
    "GOOGLE": 50,
    "VERTEX_AI": 50,
    "GEMINI": 50,
    "XAI": 50,
    "MISTRAL": 38,
    "DEEPSEEK": 38,
    "COHERE": 38,
    "GROQ": 30,
    "TOGETHER_AI": 28,
    "FIREWORKS_AI": 28,
    "PERPLEXITY": 28,
    "MINIMAX": 28,
    "BEDROCK": 28,
    "OPENROUTER": 25,
    "OLLAMA": 12,
    "CUSTOM": 12,
}


# ---------------------------------------------------------------------------
# Pure scoring helpers
# ---------------------------------------------------------------------------

# Calibrated against the live /api/v1/models bulk dump. Frontier models
# released in the last ~6 months (GPT-5 family, Claude 4.x, Gemini 2.5,
# Grok 4) score in the 18-20 band; mid-2024 models in the 8-12 band;
# anything older trails off.
_RECENCY_BANDS_DAYS: tuple[tuple[int, int], ...] = (
    (60, 20),
    (180, 16),
    (365, 12),
    (540, 9),
    (730, 6),
    (1095, 3),
)


def created_recency_signal(created_ts: int | None, now_ts: int) -> int:
    """Return 0-20 based on how recently the model was published.

    Uses the OpenRouter ``created`` Unix timestamp (or any equivalent for
    YAML cfgs). Models without a usable timestamp get 0 (we don't penalise,
    we just don't reward).
    """
    if created_ts is None or created_ts <= 0 or now_ts <= 0:
        return 0
    age_days = max(0, (now_ts - int(created_ts)) // 86_400)
    for cutoff, score in _RECENCY_BANDS_DAYS:
        if age_days <= cutoff:
            return score
    return 0


def pricing_band(
    prompt: str | float | int | None,
    completion: str | float | int | None,
) -> int:
    """Return 0-15 based on combined prompt+completion cost per 1M tokens.

    Higher-priced models tend to be the larger / more capable ones. A free
    model returns 0 (we use other signals to rank free-vs-free instead).
    Uncoercible inputs are treated as 0 rather than raising.
    """

    def _to_float(value) -> float:
        if value is None:
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    p = _to_float(prompt)
    c = _to_float(completion)
    total_per_million = (p + c) * 1_000_000

    if total_per_million >= 20.0:
        return 15
    if total_per_million >= 5.0:
        return 12
    if total_per_million >= 1.0:
        return 9
    if total_per_million >= 0.3:
        return 6
    if total_per_million >= 0.05:
        return 4
    if total_per_million > 0.0:
        return 2
    return 0


def context_signal(ctx: int | None) -> int:
    """Return 0-10 based on the model's context window."""
    if not ctx or ctx <= 0:
        return 0
    if ctx >= 1_000_000:
        return 10
    if ctx >= 400_000:
        return 8
    if ctx >= 200_000:
        return 6
    if ctx >= 128_000:
        return 4
    if ctx >= 100_000:
        return 2
    return 0


def capabilities_signal(supported_parameters: list[str] | None) -> int:
    """Return 0-5 for capabilities that matter for our agent flows."""
    if not supported_parameters:
        return 0
    params = set(supported_parameters)
    score = 0
    if "tools" in params:
        score += 2
    if "structured_outputs" in params or "response_format" in params:
        score += 2
    if "reasoning" in params or "include_reasoning" in params:
        score += 1
    return min(score, 5)


def slug_penalty(model_id: str) -> int:
    """Return a non-positive number; matches the narrow tiny/legacy patterns."""
    if not model_id:
        return 0
    needle = model_id.lower()
    for pattern in _TINY_LEGACY_PENALTY_PATTERNS:
        if pattern in needle:
            return -10
    return 0


def _provider_prestige_or(model_id: str) -> int:
    if "/" not in model_id:
        return 0
    slug = model_id.split("/", 1)[0].lower()
    return PROVIDER_PRESTIGE_OR.get(slug, 15)


def static_score_or(or_model: dict, *, now_ts: int) -> int:
    """Score a raw OpenRouter ``/api/v1/models`` entry on a 0-100 scale."""
    model_id = str(or_model.get("id", ""))
    pricing = or_model.get("pricing") or {}

    score = (
        _provider_prestige_or(model_id)
        + created_recency_signal(or_model.get("created"), now_ts)
        + pricing_band(pricing.get("prompt"), pricing.get("completion"))
        + context_signal(or_model.get("context_length"))
        + capabilities_signal(or_model.get("supported_parameters"))
        + slug_penalty(model_id)
    )
    return max(0, min(100, int(score)))


def static_score_yaml(cfg: dict) -> int:
    """Score a YAML-curated cfg on a 0-100 scale.

    Includes ``_OPERATOR_TRUST_BONUS`` because the operator deliberately
    listed this model. Pricing / context fall through to lazy ``litellm``
    lookups; failures are silent (we just lose those sub-points).
    """
    provider = str(cfg.get("provider", "")).upper()
    base = PROVIDER_PRESTIGE_YAML.get(provider, 15)

    model_name = cfg.get("model_name") or ""
    litellm_params = cfg.get("litellm_params") or {}
    lookup_name = (
        litellm_params.get("base_model")
        or litellm_params.get("model")
        or model_name
    )

    ctx = 0
    p_cost: float = 0.0
    c_cost: float = 0.0
    try:
        from litellm import get_model_info  # lazy: avoid cold-import cost

        info = get_model_info(lookup_name) or {}
        ctx = int(info.get("max_input_tokens") or info.get("max_tokens") or 0)
        p_cost = float(info.get("input_cost_per_token") or 0.0)
        c_cost = float(info.get("output_cost_per_token") or 0.0)
    except Exception:
        # Unknown to litellm — that's fine for prestige+operator-bonus weighting.
        pass

    score = (
        base
        + _OPERATOR_TRUST_BONUS
        + pricing_band(p_cost, c_cost)
        + context_signal(ctx)
        + slug_penalty(str(model_name))
    )
    return max(0, min(100, int(score)))


# ---------------------------------------------------------------------------
# Health aggregation
# ---------------------------------------------------------------------------


def _coerce_pct(value) -> float | None:
    try:
        if value is None:
            return None
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f < 0:
        return None
    # OpenRouter reports uptime as a 0-1 fraction; some endpoints surface it
    # as a 0-100 percentage. Normalise.
    return f * 100.0 if f <= 1.0 else f


def _best_uptime(endpoints: list[dict]) -> tuple[float | None, str | None]:
    """Pick the best (highest) non-null uptime across all endpoints.

    Window preference: ``uptime_last_30m`` > ``uptime_last_1d`` >
    ``uptime_last_5m``. Returns ``(uptime_pct, window_used)``.
    """
    for window in ("uptime_last_30m", "uptime_last_1d", "uptime_last_5m"):
        values = [_coerce_pct(ep.get(window)) for ep in endpoints]
        values = [v for v in values if v is not None]
        if values:
            return max(values), window
    return None, None


def aggregate_health(endpoints: list[dict]) -> tuple[bool, float | None]:
    """Aggregate a model's per-endpoint health into ``(gated, score_or_none)``.

    Hard gate (returns ``(True, None)``):
      * ``endpoints`` empty,
      * no endpoint reports ``status == 0`` (OK), or
      * best non-null uptime below ``_HEALTH_GATE_UPTIME_PCT``.

    On a pass, returns a 0-100 health score blending uptime, status, and a
    freshness-weighted recent uptime sample.
    """
    if not endpoints:
        return True, None

    any_ok = any(int(ep.get("status", 1)) == 0 for ep in endpoints)
    if not any_ok:
        return True, None

    best_uptime, _ = _best_uptime(endpoints)
    if best_uptime is None or best_uptime < _HEALTH_GATE_UPTIME_PCT:
        return True, None

    # Freshness term: prefer 5m, fall through to 30m / 1d if 5m is missing.
    freshness = None
    for window in ("uptime_last_5m", "uptime_last_30m", "uptime_last_1d"):
        values = [_coerce_pct(ep.get(window)) for ep in endpoints]
        values = [v for v in values if v is not None]
        if values:
            freshness = max(values)
            break

    uptime_term = best_uptime
    status_term = 100.0 if any_ok else 0.0
    freshness_term = freshness if freshness is not None else best_uptime

    score = 0.50 * uptime_term + 0.30 * status_term + 0.20 * freshness_term
    return False, max(0.0, min(100.0, score))
