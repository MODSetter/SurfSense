"""End-to-end smoke test for vision / image config wiring.

Loads the live ``global_llm_config.yaml`` (no mocking, no fixtures) and
exercises every chat / vision / image-generation config + the OpenRouter
dynamic catalog. For each config the script:

1. Reports the resolver classification (catalog-allow vs strict-block).
2. Optionally fires a tiny live API call against the provider:
   - Chat configs: ``litellm.acompletion`` with a 1x1 PNG and the prompt
     ``"reply with one word: ok"``.
   - Vision configs: same, against the dedicated vision router pool.
   - Image-gen configs: ``litellm.aimage_generation`` with a single tiny
     prompt and ``n=1``.
   - OpenRouter integration: samples one chat, one vision, one image-gen
     model from the dynamically fetched catalog.

Usage::

    python -m scripts.verify_chat_image_capability             # capability + connectivity
    python -m scripts.verify_chat_image_capability --no-live   # capability resolver only

The script is meant to be runnable from the repository root or from
``surfsense_backend/`` and prints a short PASS/FAIL/SKIP summary at the
end so it's usable as a CI smoke check too.

Live-mode caveat: each successful call costs a small amount of provider
credit (a few tokens or one tiny generated image per config). The
default size for image generation is ``1024x1024`` because Azure
GPT-image deployments reject smaller sizes; OpenRouter image-gen models
generally accept the same size.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

# Bootstrap the surfsense_backend package on sys.path so the script runs
# from the repo root or from `surfsense_backend/` interchangeably.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

import litellm  # noqa: E402

from app.config import config  # noqa: E402
from app.services.openrouter_integration_service import (  # noqa: E402
    _OPENROUTER_DYNAMIC_MARKER,
    OpenRouterIntegrationService,
)
from app.services.provider_api_base import resolve_api_base  # noqa: E402
from app.services.provider_capabilities import (  # noqa: E402
    derive_supports_image_input,
    is_known_text_only_chat_model,
)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
# Quiet down LiteLLM's verbose router/cost logs so the script output is
# scannable.
logging.getLogger("LiteLLM").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)

# 1x1 transparent PNG — used as the cheapest possible vision payload.
_TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
_TINY_PNG_DATA_URL = f"data:image/png;base64,{_TINY_PNG_B64}"


# ---------------------------------------------------------------------------
# Result accounting
# ---------------------------------------------------------------------------


@dataclass
class ProbeResult:
    label: str
    surface: str
    config_id: int | str
    capability_ok: bool | None = None
    capability_note: str = ""
    live_ok: bool | None = None
    live_note: str = ""
    duration_s: float = 0.0


@dataclass
class Report:
    results: list[ProbeResult] = field(default_factory=list)

    def add(self, r: ProbeResult) -> None:
        self.results.append(r)

    def render(self) -> int:
        passed = failed = skipped = 0
        print()
        print("=" * 92)
        print(
            f"{'Surface':<14}{'ID':>8}  {'Cap':>5}  {'Live':>5}  {'Time':>6}  Label  /  notes"
        )
        print("-" * 92)
        for r in self.results:

            def _flag(value: bool | None) -> str:
                if value is None:
                    return "skip"
                return "ok" if value else "fail"

            cap = _flag(r.capability_ok)
            live = _flag(r.live_ok)
            if r.capability_ok is False or r.live_ok is False:
                failed += 1
            elif r.capability_ok is None and r.live_ok is None:
                skipped += 1
            else:
                passed += 1
            print(
                f"{r.surface:<14}{r.config_id!s:>8}  {cap:>5}  {live:>5}  "
                f"{r.duration_s:>5.2f}s  {r.label}"
            )
            if r.capability_note:
                print(f"               cap:  {r.capability_note}")
            if r.live_note:
                print(f"               live: {r.live_note}")
        print("-" * 92)
        print(
            f"Total: {passed} ok / {failed} fail / {skipped} skip "
            f"(of {len(self.results)} probes)"
        )
        print("=" * 92)
        return failed


# ---------------------------------------------------------------------------
# Capability probes (no network)
# ---------------------------------------------------------------------------


def _probe_chat_capability(cfg: dict) -> tuple[bool, str]:
    """For chat configs the catalog flag is *expected* True (vision-capable
    pool). The probe reports both the resolver value and the strict
    safety-net value to surface any drift between them."""
    litellm_params = cfg.get("litellm_params") or {}
    base_model = (
        litellm_params.get("base_model") if isinstance(litellm_params, dict) else None
    )
    cap = derive_supports_image_input(
        provider=cfg.get("provider"),
        model_name=cfg.get("model_name"),
        base_model=base_model,
        custom_provider=cfg.get("custom_provider"),
    )
    block = is_known_text_only_chat_model(
        provider=cfg.get("provider"),
        model_name=cfg.get("model_name"),
        base_model=base_model,
        custom_provider=cfg.get("custom_provider"),
    )
    note = f"derive={cap} strict_block={block}"
    if not cap and not block:
        # Resolver said False but strict gate is also False — that means
        # OR modalities published [text] explicitly. Surface it.
        note += " (OR modality says text-only)"
    # We accept a True derive *or* (False derive AND False block) as
    # 'capability ok' — either way, the streaming task will flow through.
    ok = cap or not block
    return ok, note


def _build_chat_model_string(cfg: dict) -> str:
    if cfg.get("custom_provider"):
        return f"{cfg['custom_provider']}/{cfg['model_name']}"
    from app.services.provider_capabilities import _PROVIDER_PREFIX_MAP

    prefix = _PROVIDER_PREFIX_MAP.get(
        (cfg.get("provider") or "").upper(), (cfg.get("provider") or "").lower()
    )
    return f"{prefix}/{cfg['model_name']}"


# ---------------------------------------------------------------------------
# Live probes (network calls)
# ---------------------------------------------------------------------------


async def _live_chat_image_call(cfg: dict) -> tuple[bool, str]:
    """Send a 1x1 PNG + `reply with one word: ok` to the chat config."""
    model_string = _build_chat_model_string(cfg)
    api_base = resolve_api_base(
        provider=cfg.get("provider"),
        provider_prefix=model_string.split("/", 1)[0],
        config_api_base=cfg.get("api_base") or None,
    )
    kwargs: dict[str, Any] = {
        "model": model_string,
        "api_key": cfg.get("api_key"),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "reply with one word: ok"},
                    {
                        "type": "image_url",
                        "image_url": {"url": _TINY_PNG_DATA_URL},
                    },
                ],
            }
        ],
        "max_tokens": 16,
        "timeout": 60,
    }
    if api_base:
        kwargs["api_base"] = api_base
    if cfg.get("litellm_params"):
        # Strip pricing keys — they're tracking-only and confuse some
        # provider validators (e.g. azure/openai reject unknown kwargs
        # in strict mode).
        merged = {
            k: v
            for k, v in dict(cfg["litellm_params"]).items()
            if k
            not in {
                "input_cost_per_token",
                "output_cost_per_token",
                "input_cost_per_pixel",
                "output_cost_per_pixel",
            }
        }
        kwargs.update(merged)
    try:
        resp = await litellm.acompletion(**kwargs)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    text = resp.choices[0].message.content if resp.choices else ""
    return True, f"got reply ({(text or '').strip()[:40]!r})"


# Gemini image models occasionally return zero-length ``data`` for the
# minimal "red dot on white" prompt (provider-side safety / empty-output
# quirk reproducible against ``google/gemini-2.5-flash-image`` even when
# the request itself succeeds). Use a more naturalistic prompt and
# retry once with a different one before giving up.
_IMAGE_GEN_PROMPTS: tuple[str, ...] = (
    "A simple icon of a coffee cup, flat illustration",
    "A small green leaf on a white background",
)


async def _live_image_gen_call(cfg: dict) -> tuple[bool, str]:
    """Generate one tiny image to verify the deployment is reachable."""
    from app.services.provider_capabilities import _PROVIDER_PREFIX_MAP

    if cfg.get("custom_provider"):
        prefix = cfg["custom_provider"]
    else:
        prefix = _PROVIDER_PREFIX_MAP.get(
            (cfg.get("provider") or "").upper(), (cfg.get("provider") or "").lower()
        )
    model_string = f"{prefix}/{cfg['model_name']}"
    api_base = resolve_api_base(
        provider=cfg.get("provider"),
        provider_prefix=prefix,
        config_api_base=cfg.get("api_base") or None,
    )
    base_kwargs: dict[str, Any] = {
        "model": model_string,
        "api_key": cfg.get("api_key"),
        "n": 1,
        "size": "1024x1024",
        "timeout": 120,
    }
    if api_base:
        base_kwargs["api_base"] = api_base
    if cfg.get("api_version"):
        base_kwargs["api_version"] = cfg["api_version"]
    if cfg.get("litellm_params"):
        base_kwargs.update(
            {
                k: v
                for k, v in dict(cfg["litellm_params"]).items()
                if k
                not in {
                    "input_cost_per_token",
                    "output_cost_per_token",
                    "input_cost_per_pixel",
                    "output_cost_per_pixel",
                }
            }
        )

    last_note = ""
    for attempt, prompt in enumerate(_IMAGE_GEN_PROMPTS, start=1):
        try:
            resp = await litellm.aimage_generation(prompt=prompt, **base_kwargs)
        except Exception as exc:
            last_note = f"{type(exc).__name__}: {exc}"
            continue
        data_count = len(getattr(resp, "data", None) or [])
        if data_count > 0:
            return True, (
                f"received {data_count} image(s) on attempt {attempt} "
                f"(prompt={prompt!r})"
            )
        last_note = (
            f"call ok but received 0 images on attempt {attempt} (prompt={prompt!r})"
        )
    return False, last_note


# ---------------------------------------------------------------------------
# Probe drivers
# ---------------------------------------------------------------------------


def _is_or_dynamic(cfg: dict) -> bool:
    return bool(cfg.get(_OPENROUTER_DYNAMIC_MARKER))


async def probe_chat_configs(report: Report, *, live: bool) -> None:
    print("\n[chat configs from global_llm_configs (YAML-static)]")
    for cfg in config.GLOBAL_LLM_CONFIGS:
        # Skip OR dynamic entries here — handled in the OR section so
        # the YAML / OR split stays clear in the report.
        if _is_or_dynamic(cfg):
            continue
        result = ProbeResult(
            label=str(cfg.get("name") or cfg.get("model_name")),
            surface="chat-yaml",
            config_id=cfg.get("id"),
        )
        cap_ok, cap_note = _probe_chat_capability(cfg)
        result.capability_ok = cap_ok
        result.capability_note = cap_note
        if live:
            t0 = time.perf_counter()
            ok, note = await _live_chat_image_call(cfg)
            result.live_ok = ok
            result.live_note = note
            result.duration_s = time.perf_counter() - t0
        report.add(result)


async def probe_vision_configs(report: Report, *, live: bool) -> None:
    print("\n[vision configs from global_vision_llm_configs (YAML-static)]")
    for cfg in config.GLOBAL_VISION_LLM_CONFIGS:
        if _is_or_dynamic(cfg):
            continue
        result = ProbeResult(
            label=str(cfg.get("name") or cfg.get("model_name")),
            surface="vision",
            config_id=cfg.get("id"),
        )
        # For vision configs, capability is implied — they're in the
        # dedicated vision pool. Run the same resolver to flag any
        # surprise disagreement.
        cap_ok, cap_note = _probe_chat_capability(cfg)
        result.capability_ok = cap_ok
        result.capability_note = cap_note
        if live:
            t0 = time.perf_counter()
            ok, note = await _live_chat_image_call(cfg)
            result.live_ok = ok
            result.live_note = note
            result.duration_s = time.perf_counter() - t0
        report.add(result)


async def probe_image_gen_configs(report: Report, *, live: bool) -> None:
    print(
        "\n[image generation configs from global_image_generation_configs (YAML-static)]"
    )
    for cfg in config.GLOBAL_IMAGE_GEN_CONFIGS:
        if _is_or_dynamic(cfg):
            continue
        result = ProbeResult(
            label=str(cfg.get("name") or cfg.get("model_name")),
            surface="image-gen",
            config_id=cfg.get("id"),
        )
        # Image gen configs don't have a "supports_image_input" flag;
        # the catalog tracks output, not input. Mark capability as None
        # (skip) for the report.
        if live:
            t0 = time.perf_counter()
            ok, note = await _live_image_gen_call(cfg)
            result.live_ok = ok
            result.live_note = note
            result.duration_s = time.perf_counter() - t0
        report.add(result)


async def probe_openrouter_catalog(report: Report, *, live: bool) -> None:
    """Sample one chat (vision-capable), one vision, one image-gen model
    from the live OpenRouter catalogue. Doesn't iterate the full pool
    (would be hundreds of probes); just validates the integration end-
    to-end on a representative model from each surface."""
    print("\n[OpenRouter integration: sampled probes]")
    settings = config.OPENROUTER_INTEGRATION_SETTINGS
    if not settings:
        report.add(
            ProbeResult(
                label="OpenRouter integration",
                surface="openrouter",
                config_id="settings",
                capability_ok=None,
                capability_note="openrouter_integration disabled in YAML — skipping",
                live_ok=None,
            )
        )
        return

    service = OpenRouterIntegrationService.get_instance()
    or_chat = [
        c
        for c in config.GLOBAL_LLM_CONFIGS
        if c.get("provider") == "OPENROUTER" and c.get("supports_image_input")
    ]
    or_vision = [
        c for c in config.GLOBAL_VISION_LLM_CONFIGS if c.get("provider") == "OPENROUTER"
    ]
    or_image_gen = [
        c for c in config.GLOBAL_IMAGE_GEN_CONFIGS if c.get("provider") == "OPENROUTER"
    ]

    # Pick one representative per provider family per surface so a single
    # broken vendor (e.g. Anthropic key revoked, Google quota exceeded)
    # surfaces independently of the others. Each needle matches the
    # OpenRouter ``model_name`` prefix; the first match wins.
    def _pick_first(pool: list[dict], needle: str) -> dict | None:
        for c in pool:
            if (c.get("model_name") or "").lower().startswith(needle):
                return c
        return None

    chat_picks = [
        ("or-chat", _pick_first(or_chat, "openai/gpt-4o")),
        ("or-chat", _pick_first(or_chat, "anthropic/claude")),
        ("or-chat", _pick_first(or_chat, "google/gemini-2.5-flash")),
    ]
    vision_picks = [
        ("or-vision", _pick_first(or_vision, "openai/gpt-4o")),
        ("or-vision", _pick_first(or_vision, "anthropic/claude")),
        ("or-vision", _pick_first(or_vision, "google/gemini-2.5-flash")),
    ]
    image_picks = [
        ("or-image", _pick_first(or_image_gen, "google/gemini-2.5-flash-image")),
        # OpenRouter publishes OpenAI image models as ``openai/gpt-5-image*``
        # / ``openai/gpt-5.4-image-2`` (no ``gpt-image`` literal). Match
        # the actual prefix.
        ("or-image", _pick_first(or_image_gen, "openai/gpt-5-image")),
    ]

    print(
        f"  catalog: chat={len(or_chat)} vision={len(or_vision)} image_gen={len(or_image_gen)} "
        f"(service initialized={service.is_initialized() if hasattr(service, 'is_initialized') else 'n/a'})"
    )

    for surface, picked in chat_picks + vision_picks + image_picks:
        if not picked:
            report.add(
                ProbeResult(
                    label=f"<no candidate for {surface}>",
                    surface=surface,
                    config_id="-",
                    capability_ok=None,
                    capability_note="no candidate found in OR catalog",
                )
            )
            continue
        runner = (
            _live_image_gen_call if surface == "or-image" else _live_chat_image_call
        )
        result = ProbeResult(
            label=str(picked.get("model_name")),
            surface=surface,
            config_id=picked.get("id"),
        )
        if surface != "or-image":
            cap_ok, cap_note = _probe_chat_capability(picked)
            result.capability_ok = cap_ok
            result.capability_note = cap_note
        if live:
            t0 = time.perf_counter()
            ok, note = await runner(picked)
            result.live_ok = ok
            result.live_note = note
            result.duration_s = time.perf_counter() - t0
        report.add(result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> int:
    print("Loaded global configs:")
    print(f"  chat:      {len(config.GLOBAL_LLM_CONFIGS)} entries")
    print(f"  vision:    {len(config.GLOBAL_VISION_LLM_CONFIGS)} entries")
    print(f"  image-gen: {len(config.GLOBAL_IMAGE_GEN_CONFIGS)} entries")
    print(f"  OR settings present: {bool(config.OPENROUTER_INTEGRATION_SETTINGS)}")

    # Initialize the OpenRouter integration so the catalog is populated
    # (this is what main.py does at startup). It's idempotent.
    if config.OPENROUTER_INTEGRATION_SETTINGS:
        try:
            from app.config import initialize_openrouter_integration

            initialize_openrouter_integration()
        except Exception as exc:
            print(f"  WARNING: OpenRouter integration init failed: {exc}")

    print(
        f"\nMode: {'LIVE (will hit providers)' if args.live else 'DRY (capability only)'}"
    )

    report = Report()
    if not args.skip_chat:
        await probe_chat_configs(report, live=args.live)
    if not args.skip_vision:
        await probe_vision_configs(report, live=args.live)
    if not args.skip_image_gen:
        await probe_image_gen_configs(report, live=args.live)
    if not args.skip_openrouter:
        await probe_openrouter_catalog(report, live=args.live)

    failed = report.render()
    return 1 if failed else 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-live",
        dest="live",
        action="store_false",
        help="Skip live API calls — capability resolver only.",
    )
    parser.set_defaults(live=True)
    parser.add_argument("--skip-chat", action="store_true")
    parser.add_argument("--skip-vision", action="store_true")
    parser.add_argument("--skip-image-gen", action="store_true")
    parser.add_argument("--skip-openrouter", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(asyncio.run(main(args)))
