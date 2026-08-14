"""Confirm against live OpenRouter that the models Auto keeps picking are dead.

PostHog attributes ``MODEL_NOT_FOUND`` to two families:

- ``:batch`` variants (``*:batch``), which OpenRouter lists in ``/models`` with
  full chat metadata but routes to an asynchronous batch API. 1,829 of 1,829
  generations failed.
- Models delisted upstream since our last process restart
  (``poolside/laguna-m.1``, ``openai/gpt-5.3-chat``).

This script settles both without reading any more dashboards: it fires one
real chat completion per suspect id and prints the HTTP status. A known-good
control model runs alongside so a blanket 401 can never be mistaken for
per-model 404s.

Usage::

    python -m scripts.probe_openrouter_dead_models              # catalogue + live calls
    python -m scripts.probe_openrouter_dead_models --no-live    # catalogue only, free

Live mode costs a few cents at most (one ``max_tokens=1`` call per model).
Kept out of CI on purpose: the suite must not depend on OpenRouter being up.

Key resolution order: ``--api-key``, ``$OPENROUTER_API_KEY``, then
``openrouter_integration.api_key`` from the live ``global_llm_config.yaml``.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

import httpx  # noqa: E402

from app.services.openrouter_model_normalizer import (  # noqa: E402
    is_openrouter_chat_model,
)

MODELS_URL = "https://openrouter.ai/api/v1/models"
COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"

# Delisted upstream, still selectable until a restart because ``refresh()``
# never re-materializes GLOBAL_MODELS.
DELISTED_IDS = ("poolside/laguna-m.1", "openai/gpt-5.3-chat")

# Distinguishes a per-model 404 from an account-wide auth or billing failure.
CONTROL_ID = "openai/gpt-4o-mini"


def _resolve_api_key(cli_key: str | None) -> str:
    if cli_key:
        return cli_key
    env_key = os.environ.get("OPENROUTER_API_KEY")
    if env_key:
        return env_key
    try:
        from app.config import load_openrouter_integration_settings

        settings = load_openrouter_integration_settings() or {}
        return str(settings.get("api_key") or "")
    except Exception as exc:
        print(f"  (could not read global_llm_config.yaml: {exc})")
        return ""


async def _fetch_catalogue() -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(MODELS_URL)
        resp.raise_for_status()
        return resp.json().get("data", [])


def _report_catalogue(raw_models: list[dict]) -> list[str]:
    """Print how many ``:batch`` variants our live filter currently admits."""
    batch = [m for m in raw_models if str(m.get("id") or "").endswith(":batch")]
    admitted = [m for m in batch if is_openrouter_chat_model(m)]

    print(f"\ncatalogue: {len(raw_models)} models, {len(batch)} `:batch` variants")
    print(f"  admitted by is_openrouter_chat_model: {len(admitted)}")
    for model in admitted[:10]:
        print(f"    {model['id']}")
    if len(admitted) > 10:
        print(f"    ... and {len(admitted) - 10} more")

    listed = {str(m.get("id") or "") for m in raw_models}
    for model_id in DELISTED_IDS:
        state = "STILL LISTED" if model_id in listed else "absent (delisted)"
        print(f"  {model_id}: {state}")

    return [str(m["id"]) for m in admitted]


async def _probe(client: httpx.AsyncClient, api_key: str, model_id: str) -> str:
    """Fire one minimal completion and return a short status line."""
    try:
        resp = await client.post(
            COMPLETIONS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
            },
        )
    except Exception as exc:
        return f"transport error: {type(exc).__name__}: {exc}"

    # OpenRouter returns 200 with an ``error`` body for some routing failures,
    # so the status code alone does not tell us whether the model answered.
    body = resp.text[:200].replace("\n", " ")
    if resp.status_code == 200:
        try:
            payload = resp.json()
        except Exception:
            payload = {}
        if isinstance(payload, dict) and payload.get("error"):
            return f"HTTP 200 but error body: {payload['error']}"
        return "HTTP 200 OK"
    return f"HTTP {resp.status_code}: {body}"


async def run(*, live: bool, api_key: str) -> int:
    raw_models = await _fetch_catalogue()
    admitted_batch = _report_catalogue(raw_models)

    if not live:
        print("\n--no-live: skipping completion calls")
        return 0

    if not api_key:
        print("\nNo OpenRouter API key found; cannot run live probes.")
        return 2

    targets = [CONTROL_ID, *DELISTED_IDS]
    if admitted_batch:
        targets.insert(1, admitted_batch[0])
    else:
        print("\nNo `:batch` variant passes the filter right now; probing a known id.")
        targets.insert(1, "anthropic/claude-sonnet-4.5:batch")

    print("\nlive probes:")
    async with httpx.AsyncClient(timeout=60) as client:
        for model_id in targets:
            status = await _probe(client, api_key, model_id)
            label = "control" if model_id == CONTROL_ID else "suspect"
            print(f"  [{label}] {model_id}\n      {status}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-live",
        action="store_true",
        help="Only inspect the catalogue; make no completion calls.",
    )
    parser.add_argument("--api-key", default=None, help="OpenRouter API key.")
    args = parser.parse_args()

    return asyncio.run(
        run(live=not args.no_live, api_key=_resolve_api_key(args.api_key))
    )


if __name__ == "__main__":
    raise SystemExit(main())
