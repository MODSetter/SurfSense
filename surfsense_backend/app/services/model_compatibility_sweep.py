"""Probe catalogue models for real turn compatibility and record the verdicts.

Passing our metadata filters only proves a model *claims* to support tool
calling and a large enough context. It does not prove it works here: ``:batch``
ids answer 404, delisted ids answer 404, and some providers accept ``tools``
but reject the message history an agent turn produces once a tool has run.

Each model gets up to three escalating probes, stopping at the first failure:

1. ``stream`` — a streaming hello that must produce at least one chunk.
2. ``tool_bind`` — the same call with two dummy tools bound, which must return
   either a well-formed ``tool_call`` or clean text.
3. ``tool_result`` — the assistant tool-call message plus its tool result fed
   back in, which must produce a final answer.

Lives in ``app/`` rather than ``scripts/`` because both the CLI
(``scripts/sweep_model_compatibility.py``) and the periodic Celery task run it.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

import httpx
import litellm
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.services.model_compatibility import (
    CompatibilityStatus,
    CompatibilityVerdict,
    ProbeStage,
    verdict_from_stages,
)
from app.services.openrouter_model_normalizer import normalize_openrouter_models

logger = logging.getLogger(__name__)

MODELS_URL = "https://openrouter.ai/api/v1/models"
API_BASE = "https://openrouter.ai/api/v1"
PROBE_TIMEOUT_SEC = 60
DEFAULT_CONCURRENCY = 8
DEFAULT_MAX_AGE_DAYS = 30

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current time in a timezone.",
            "parameters": {
                "type": "object",
                "properties": {"timezone": {"type": "string"}},
                "required": ["timezone"],
            },
        },
    },
]

_TOOL_CALL_ID = "call_sweep_1"


class ProbeResponseError(RuntimeError):
    """A probe reached the provider but the response was unusable.

    Carries no provider status code, so ``classify_probe_failure`` leaves it
    ``UNKNOWN``: an empty reply is suspicious, not proof the model is dead.
    """


def _kwargs(model_id: str, api_key: str) -> dict:
    return {
        "model": f"openrouter/{model_id}",
        "api_key": api_key,
        "api_base": API_BASE,
        "timeout": PROBE_TIMEOUT_SEC,
        "max_tokens": 64,
    }


async def _probe_stream(model_id: str, api_key: str) -> None:
    stream = await litellm.acompletion(
        **_kwargs(model_id, api_key),
        messages=[{"role": "user", "content": "Reply with the single word: ok"}],
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta is not None and (getattr(delta, "content", None) or ""):
            return
    raise ProbeResponseError("stream produced no content")


async def _probe_tool_bind(model_id: str, api_key: str) -> None:
    response = await litellm.acompletion(
        **_kwargs(model_id, api_key),
        messages=[
            {"role": "user", "content": "What is the weather in Paris? Use your tools."}
        ],
        tools=_TOOLS,
        tool_choice="auto",
    )
    message = response.choices[0].message if response.choices else None
    if message is None:
        raise ProbeResponseError("no choices returned with tools bound")
    for call in getattr(message, "tool_calls", None) or []:
        # A malformed call is worse than no call: the agent crashes mid-turn
        # instead of falling back to prose.
        if not getattr(call.function, "name", None):
            raise ProbeResponseError("tool_call missing a function name")
        return
    if not (message.content or "").strip():
        raise ProbeResponseError("neither a tool call nor text with tools bound")


async def _probe_tool_result(model_id: str, api_key: str) -> None:
    response = await litellm.acompletion(
        **_kwargs(model_id, api_key),
        messages=[
            {"role": "user", "content": "What is the weather in Paris?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": _TOOL_CALL_ID,
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"city": "Paris"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": _TOOL_CALL_ID,
                "name": "get_weather",
                "content": "18C and clear",
            },
        ],
        tools=_TOOLS,
    )
    message = response.choices[0].message if response.choices else None
    if message is None or not (message.content or "").strip():
        raise ProbeResponseError("no answer after a tool result")


_PROBES = {
    ProbeStage.STREAM: _probe_stream,
    ProbeStage.TOOL_BIND: _probe_tool_bind,
    ProbeStage.TOOL_RESULT: _probe_tool_result,
}


async def probe_model(model_id: str, api_key: str) -> tuple[CompatibilityVerdict, int]:
    """Run the stages in order, stopping at the first failure."""
    started = time.monotonic()
    results: dict[ProbeStage, BaseException | None] = {}
    for stage, probe in _PROBES.items():
        try:
            await probe(model_id, api_key)
        except Exception as exc:
            results[stage] = exc
            break
        results[stage] = None
    return verdict_from_stages(results), int((time.monotonic() - started) * 1000)


async def fetch_catalogue_model_ids() -> list[str]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(MODELS_URL)
        response.raise_for_status()
        raw_models = response.json().get("data", [])
    return [m["model_id"] for m in normalize_openrouter_models(raw_models)]


def resolve_api_key() -> str:
    import os

    from app.config import load_openrouter_integration_settings

    env_key = os.environ.get("OPENROUTER_API_KEY")
    if env_key:
        return env_key
    settings = load_openrouter_integration_settings() or {}
    return str(settings.get("api_key") or "")


async def recently_checked_ids(max_age_days: int) -> set[str]:
    from app.db import ModelCompatibility, async_session_maker

    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    async with async_session_maker() as session:
        result = await session.execute(
            select(ModelCompatibility.model_id).where(
                ModelCompatibility.checked_at >= cutoff
            )
        )
        return {row[0] for row in result}


async def record_verdict(
    model_id: str, verdict: CompatibilityVerdict, latency_ms: int
) -> None:
    from app.db import ModelCompatibility, async_session_maker

    values = {
        "model_id": model_id,
        "status": verdict.status.value,
        "failure_stage": verdict.failure_stage.value if verdict.failure_stage else None,
        "error_code": verdict.error_code,
        "error_excerpt": verdict.error_excerpt,
        "latency_ms": latency_ms,
        "checked_at": datetime.now(UTC),
    }
    statement = pg_insert(ModelCompatibility).values(**values)
    statement = statement.on_conflict_do_update(
        index_elements=[ModelCompatibility.model_id],
        set_={key: value for key, value in values.items() if key != "model_id"},
    )
    async with async_session_maker() as session:
        await session.execute(statement)
        await session.commit()


async def sweep_models(
    model_ids: Iterable[str],
    *,
    api_key: str,
    concurrency: int = DEFAULT_CONCURRENCY,
    on_verdict=None,
) -> dict[str, int]:
    """Probe each model with bounded concurrency, recording every verdict.

    Returns a ``{status: count}`` tally. One model's failure never aborts the
    sweep — a run that dies halfway would leave the blocklist half-applied.
    """
    semaphore = asyncio.Semaphore(concurrency)
    counts: dict[str, int] = {status.value: 0 for status in CompatibilityStatus}

    async def sweep_one(model_id: str) -> None:
        async with semaphore:
            try:
                verdict, latency_ms = await probe_model(model_id, api_key)
            except Exception:
                logger.exception("compatibility probe crashed for %s", model_id)
                return
        counts[verdict.status.value] += 1
        try:
            await record_verdict(model_id, verdict, latency_ms)
        except Exception:
            logger.exception("could not record verdict for %s", model_id)
        if on_verdict is not None:
            on_verdict(model_id, verdict)

    await asyncio.gather(*(sweep_one(model_id) for model_id in model_ids))
    return counts


__all__ = [
    "DEFAULT_CONCURRENCY",
    "DEFAULT_MAX_AGE_DAYS",
    "ProbeResponseError",
    "fetch_catalogue_model_ids",
    "probe_model",
    "recently_checked_ids",
    "record_verdict",
    "resolve_api_key",
    "sweep_models",
]
