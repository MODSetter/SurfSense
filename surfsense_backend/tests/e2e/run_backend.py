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

import asyncio
import logging
import os
import sys

import uvicorn

# Make the surfsense_backend root importable as a top-level package so
# `import tests.e2e.fakes...` works regardless of how the entrypoint is
# invoked (uv run python tests/e2e/run_backend.py from repo root or from
# surfsense_backend/).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)


logger = logging.getLogger("surfsense.e2e.backend")

# Patches started during bootstrap are kept alive for the lifetime of the
# process. We never call .stop() on them.
_active_patches: list = []


def _hijack_external_sdks() -> None:
    """Replace composio + notion_client in sys.modules.

    Production does ``from composio import Composio`` and
    ``import notion_client`` at import time. With this hijack in place,
    those imports resolve to our strict fakes.

    MUST run before _import_production_app().
    """
    import tests.e2e.fakes.composio_module as _fake_composio
    import tests.e2e.fakes.notion_module as _fake_notion

    sys.modules["composio"] = _fake_composio
    sys.modules["notion_client"] = _fake_notion
    sys.modules["notion_client.errors"] = _fake_notion.errors


def _load_dotenv_and_set_env_defaults() -> None:
    """Load .env and set every env var the production config reads on import.

    MUST run before _import_production_app(), since app.config consumes
    these values at import time.
    """
    from dotenv import load_dotenv

    load_dotenv()

    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/surfsense",
    )
    os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
    os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    os.environ.setdefault("REDIS_APP_URL", "redis://localhost:6379/0")
    os.environ.setdefault("CELERY_TASK_DEFAULT_QUEUE", "surfsense")
    os.environ.setdefault("SECRET_KEY", "local-e2e-secret-not-for-production")
    os.environ.setdefault("AUTH_TYPE", "LOCAL")
    os.environ.setdefault("REGISTRATION_ENABLED", "TRUE")
    os.environ.setdefault("ETL_SERVICE", "DOCLING")
    os.environ.setdefault("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    os.environ.setdefault("NEXT_FRONTEND_URL", "http://localhost:3000")

    # Sentinel keys — fakes never read them; turns leaked real calls into 401s.
    os.environ.setdefault("COMPOSIO_API_KEY", "local-deny-real-call-sentinel")
    os.environ.setdefault("COMPOSIO_ENABLED", "TRUE")
    os.environ.setdefault("OPENAI_API_KEY", "local-deny-real-call-sentinel")
    os.environ.setdefault("ANTHROPIC_API_KEY", "local-deny-real-call-sentinel")
    os.environ.setdefault("LITELLM_API_KEY", "local-deny-real-call-sentinel")

    os.environ.setdefault("ATLASSIAN_CLIENT_ID", "fake-atlassian-client-id")
    os.environ.setdefault("ATLASSIAN_CLIENT_SECRET", "fake-atlassian-client-secret")
    os.environ.setdefault(
        "CONFLUENCE_REDIRECT_URI",
        "http://localhost:8000/api/v1/auth/confluence/connector/callback",
    )
    os.environ.setdefault("NOTION_CLIENT_ID", "fake-notion-client-id")
    os.environ.setdefault("NOTION_CLIENT_SECRET", "fake-notion-client-secret")
    os.environ.setdefault(
        "NOTION_REDIRECT_URI",
        "http://localhost:8000/api/v1/auth/notion/connector/callback",
    )
    os.environ.setdefault("MICROSOFT_CLIENT_ID", "fake-microsoft-client-id")
    os.environ.setdefault("MICROSOFT_CLIENT_SECRET", "fake-microsoft-client-secret")
    os.environ.setdefault(
        "ONEDRIVE_REDIRECT_URI",
        "http://localhost:8000/api/v1/auth/onedrive/connector/callback",
    )
    os.environ.setdefault("DROPBOX_APP_KEY", "fake-dropbox-app-key")
    os.environ.setdefault("DROPBOX_APP_SECRET", "fake-dropbox-app-secret")
    os.environ.setdefault(
        "DROPBOX_REDIRECT_URI",
        "http://localhost:8000/api/v1/auth/dropbox/connector/callback",
    )
    # Native Google OAuth — fake Flow in tests.e2e.fakes.native_google
    # raises "Fake Google Flow requires redirect_uri." if these are empty,
    # so connector/add routes return 500 in CI where no .env supplies them.
    os.environ.setdefault(
        "GOOGLE_DRIVE_REDIRECT_URI",
        "http://localhost:8000/api/v1/auth/google/drive/connector/callback",
    )
    os.environ.setdefault(
        "GOOGLE_GMAIL_REDIRECT_URI",
        "http://localhost:8000/api/v1/auth/google/gmail/connector/callback",
    )
    os.environ.setdefault(
        "GOOGLE_CALENDAR_REDIRECT_URI",
        "http://localhost:8000/api/v1/auth/google/calendar/connector/callback",
    )
    os.environ["SLACK_CLIENT_ID"] = "fake-slack-mcp-client-id"
    os.environ["SLACK_CLIENT_SECRET"] = "fake-slack-mcp-client-secret"


def _install_synthetic_global_llm_config() -> None:
    """Materialise a fake ``app/config/global_llm_config.yaml`` for E2E.

    The real file is gitignored (production operators ship their own with
    real API keys), so a fresh CI checkout has no YAML at the path
    ``app.config.load_global_llm_configs()`` reads. With an empty
    ``GLOBAL_LLM_CONFIGS`` list, ``auto_model_pin_service`` raises
    ``"No usable global LLM configs are available for Auto mode"`` on
    every chat-stream request.

    We copy the synthetic fixture from ``tests/e2e/fixtures/`` into the
    production-expected location BEFORE ``_import_production_app()`` so
    ``app.config`` picks it up on import. Production code is untouched —
    this is purely a test-time scaffold.

    Only installs when the destination is missing. A developer running
    the E2E entrypoint locally keeps their real ``global_llm_config.yaml``
    intact (the patched ``create_chat_litellm_from_*`` factories make the
    actual model values irrelevant either way).

    MUST run before _import_production_app().
    """
    import shutil

    src = os.path.join(_THIS_DIR, "fixtures", "global_llm_config.yaml")
    dst = os.path.join(_BACKEND_ROOT, "app", "config", "global_llm_config.yaml")

    if not os.path.exists(src):
        raise RuntimeError(
            f"E2E synthetic global LLM config fixture missing at {src!r}. "
            f"This file is checked into tests/e2e/fixtures/ — if it has gone "
            f"missing, restore it from VCS before running the E2E entrypoint."
        )

    if os.path.exists(dst):
        logger.info(
            "[e2e-global-llm-config] %s already exists; leaving it alone "
            "(local dev config preserved)",
            dst,
        )
        return

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    logger.info("[e2e-global-llm-config] installed %s -> %s", src, dst)


def _import_production_app():
    """Import and return the production FastAPI app.

    Every module under ``app.*`` loads here, creating their bindings.
    The LLM/embedding factories captured at this point will be replaced
    by patches in _patch_llm_bindings() below.
    """
    from app.app import app as production_app

    return production_app


def _patch_llm_bindings() -> None:
    """Replace LLM factories at every known binding site."""
    from unittest.mock import patch

    from tests.e2e.fakes.chat_llm import (
        fake_create_chat_litellm_from_agent_config,
        fake_create_chat_litellm_from_config,
    )
    from tests.e2e.fakes.llm import fake_get_user_long_context_llm

    targets = [
        "app.services.llm_service.get_user_long_context_llm",
        "app.tasks.connector_indexers.confluence_indexer.get_user_long_context_llm",
        "app.tasks.connector_indexers.google_drive_indexer.get_user_long_context_llm",
        "app.tasks.connector_indexers.google_gmail_indexer.get_user_long_context_llm",
        "app.tasks.connector_indexers.notion_indexer.get_user_long_context_llm",
        "app.tasks.connector_indexers.onedrive_indexer.get_user_long_context_llm",
        "app.tasks.connector_indexers.dropbox_indexer.get_user_long_context_llm",
        "app.tasks.connector_indexers.local_folder_indexer.get_user_long_context_llm",
        "app.tasks.document_processors._save.get_user_long_context_llm",
        "app.tasks.document_processors.markdown_processor.get_user_long_context_llm",
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
            "app.agents.chat.multi_agent_chat.shared.llm_config.create_chat_litellm_from_agent_config",
            fake_create_chat_litellm_from_agent_config,
        ),
        (
            "app.agents.chat.multi_agent_chat.shared.llm_config.create_chat_litellm_from_config",
            fake_create_chat_litellm_from_config,
        ),
        (
            "app.tasks.chat.streaming.flows.shared.llm_bundle.create_chat_litellm_from_agent_config",
            fake_create_chat_litellm_from_agent_config,
        ),
        (
            "app.tasks.chat.streaming.flows.shared.llm_bundle.create_chat_litellm_from_config",
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


def _install_runtime_fakes() -> None:
    """Run each fake's install() against the active patch stack."""
    from tests.e2e.fakes import (
        clickup_module as _fake_clickup_module,
        confluence_indexer as _fake_confluence_indexer,
        confluence_oauth as _fake_confluence_oauth,
        docling_service as _fake_docling_service,
        dropbox_api as _fake_dropbox_api,
        embeddings as _fake_embeddings,
        jira_module as _fake_jira_module,
        linear_module as _fake_linear_module,
        mcp_oauth_runtime as _fake_mcp_oauth_runtime,
        mcp_runtime as _fake_mcp_runtime,
        native_google as _fake_native_google,
        notion_module as _fake_notion_module,
        onedrive_graph as _fake_onedrive_graph,
        slack_module as _fake_slack_module,
    )

    _fake_embeddings.install(_active_patches)
    _fake_docling_service.install(_active_patches)
    _fake_confluence_oauth.install(_active_patches)
    _fake_confluence_indexer.install(_active_patches)
    _fake_native_google.install(_active_patches)
    _fake_onedrive_graph.install(_active_patches)
    _fake_dropbox_api.install(_active_patches)
    _fake_notion_module.install(_active_patches)
    _fake_linear_module.install(_active_patches)
    _fake_jira_module.install(_active_patches)
    _fake_clickup_module.install(_active_patches)
    _fake_mcp_runtime.install(_active_patches)
    _fake_mcp_oauth_runtime.install(_active_patches)
    _fake_slack_module.install(_active_patches)


def _install_test_only_app_extensions(app) -> None:
    """Mount test-only middleware + the /__e2e__ token mint router.

    POST /__e2e__/auth/token bypasses /auth/jwt/login's 5/min/IP rate
    limit so Playwright workers can authenticate without thrashing the
    production auth surface. See tests/e2e/auth_mint.py.
    """
    from tests.e2e.auth_mint import install as install_e2e_mint
    from tests.e2e.middleware.scenario import ScenarioMiddleware

    app.add_middleware(ScenarioMiddleware)
    install_e2e_mint(app)


def _bootstrap():
    """Run the full E2E bootstrap and return the production FastAPI app.

    Ordering is load-bearing:
      1) Hijack composio + notion_client in sys.modules.
      2) Load .env + set env defaults (app.config reads env on import).
      3) Configure logging.
      4) Materialise the synthetic global_llm_config.yaml so Auto-mode
         pin resolution finds at least one usable candidate.
      5) Import production app (which transitively imports the now-faked
         external SDKs and reads the env defaults + YAML).
      6) Patch LLM / embedding bindings at every consumer site.
      7) Mount test-only middleware + /__e2e__ routes onto the app.
    """
    _hijack_external_sdks()
    _load_dotenv_and_set_env_defaults()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.warning(
        "*** SURFSENSE E2E BACKEND ENTRYPOINT — fake Composio + LLM + embeddings ***"
    )

    _install_synthetic_global_llm_config()
    production_app = _import_production_app()
    _patch_llm_bindings()
    _install_runtime_fakes()
    _install_test_only_app_extensions(production_app)
    return production_app


app = _bootstrap()


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
