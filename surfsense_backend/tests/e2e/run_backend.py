"""E2E backend entrypoint.

Hijacks third-party SDKs at sys.modules level BEFORE any production
code is imported, then starts the same FastAPI app + uvicorn that
`main.py` would run.

Production code is byte-identical with or without this file:
- `python main.py` is the production entrypoint (unchanged).
- `python tests/e2e/run_backend.py` is the test entrypoint, never imported by production.
- `surfsense_backend/.dockerignore` excludes `tests/`, so this file
  physically does not exist in the production Docker image.

Defense in depth (see Composio Drive E2E Phase 1 plan):
1. sys.modules hijack here (Composio).
2. Strict __getattr__ inside fakes (NotImplementedError on unknown surface).
3. Network deny-list set in CI env (HTTPS_PROXY=http://127.0.0.1:1
   plus sentinel API keys) so any leaked outbound HTTP fails loudly.

Usage:
    cd surfsense_backend
    uv run python tests/e2e/run_backend.py
"""

from __future__ import annotations

import logging
import os
import sys

# ---------------------------------------------------------------------------
# 1) Hijack sys.modules BEFORE any production import.
#    Production: composio_service.py:11 does `from composio import Composio`.
#    With this hijack in place, that import resolves to our strict fake.
# ---------------------------------------------------------------------------

# Make the surfsense_backend root importable as a top-level package so
# `import tests.e2e.fakes...` works regardless of how the entrypoint is
# invoked (uv run python tests/e2e/run_backend.py from repo root or from
# surfsense_backend/).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

import tests.e2e.fakes.composio_module as _fake_composio  # noqa: E402

sys.modules["composio"] = _fake_composio


# ---------------------------------------------------------------------------
# 2) Standard logging + dotenv so the rest of the app behaves like main.py.
# ---------------------------------------------------------------------------

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("surfsense.e2e.backend")
logger.warning(
    "*** SURFSENSE E2E BACKEND ENTRYPOINT — fake Composio + LLM + embeddings, "
    "this MUST NOT be reachable in production. ***"
)


# ---------------------------------------------------------------------------
# 3) Now import the production app. Every module in app.* loads here,
#    creating their bindings (some of which we will patch in step 4).
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 4) Patch LLM + embedding bindings at every consumer site.
#    Composio is already covered by the sys.modules hijack in step 1.
# ---------------------------------------------------------------------------
from unittest.mock import patch  # noqa: E402

from app.app import app  # noqa: E402
from tests.e2e.fakes import (  # noqa: E402
    embeddings as _fake_embeddings,
    native_google as _fake_native_google,
)
from tests.e2e.fakes.chat_llm import (  # noqa: E402
    fake_create_chat_litellm_from_agent_config,
    fake_create_chat_litellm_from_config,
)
from tests.e2e.fakes.llm import fake_get_user_long_context_llm  # noqa: E402

_active_patches: list = []


def _patch_llm_bindings() -> None:
    """Replace LLM factories at every known binding site."""
    targets = [
        "app.services.llm_service.get_user_long_context_llm",
        "app.tasks.connector_indexers.google_drive_indexer.get_user_long_context_llm",
        "app.tasks.connector_indexers.google_gmail_indexer.get_user_long_context_llm",
        "app.tasks.connector_indexers.local_folder_indexer.get_user_long_context_llm",
        "app.tasks.document_processors.file_processors.get_user_long_context_llm",
    ]
    for target in targets:
        try:
            p = patch(target, fake_get_user_long_context_llm)
            p.start()
            _active_patches.append(p)
            logger.info("[fake-llm] patched %s", target)
        except (ModuleNotFoundError, AttributeError) as exc:
            # Some indexers may not be loaded in every env. Log and move
            # on — but do not silently let a known binding through.
            logger.warning(
                "[fake-llm] could not patch %s: %s. If production code "
                "uses this path in E2E it will hit the real provider; "
                "update tests/e2e/run_backend.py.",
                target,
                exc,
            )

    chat_targets = [
        (
            "app.agents.new_chat.llm_config.create_chat_litellm_from_agent_config",
            fake_create_chat_litellm_from_agent_config,
        ),
        (
            "app.agents.new_chat.llm_config.create_chat_litellm_from_config",
            fake_create_chat_litellm_from_config,
        ),
        (
            "app.tasks.chat.stream_new_chat.create_chat_litellm_from_agent_config",
            fake_create_chat_litellm_from_agent_config,
        ),
        (
            "app.tasks.chat.stream_new_chat.create_chat_litellm_from_config",
            fake_create_chat_litellm_from_config,
        ),
    ]
    for target, replacement in chat_targets:
        try:
            p = patch(target, replacement)
            p.start()
            _active_patches.append(p)
            logger.info("[fake-chat-llm] patched %s", target)
        except (ModuleNotFoundError, AttributeError) as exc:
            logger.warning("[fake-chat-llm] could not patch %s: %s.", target, exc)


_patch_llm_bindings()
_fake_embeddings.install(_active_patches)
_fake_native_google.install(_active_patches)


# ---------------------------------------------------------------------------
# 5) Mount test-only middleware. Production never reaches this code.
# ---------------------------------------------------------------------------

from tests.e2e.middleware.scenario import ScenarioMiddleware  # noqa: E402

app.add_middleware(ScenarioMiddleware)


# ---------------------------------------------------------------------------
# 6) Start uvicorn, mirroring main.py's behaviour.
# ---------------------------------------------------------------------------

import asyncio  # noqa: E402

import uvicorn  # noqa: E402


def _main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    host = os.getenv("UVICORN_HOST", "0.0.0.0")
    port = int(os.getenv("UVICORN_PORT", "8000"))
    log_level = os.getenv("UVICORN_LOG_LEVEL", "info")

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level=log_level,
        reload=False,
    )
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    _main()
