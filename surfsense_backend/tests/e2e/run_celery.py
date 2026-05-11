"""E2E Celery worker entrypoint.

Same sys.modules hijack + LLM/embedding patches as run_backend.py,
applied before importing the production celery_app. Celery workers
run in a separate Python interpreter, so the patches must be applied
here too — they would NOT carry over from the FastAPI process.

Production is unaffected: celery_worker.py at the repo root is the
production entrypoint and never imports this file.

Usage:
    cd surfsense_backend
    uv run python tests/e2e/run_celery.py
"""

from __future__ import annotations

import logging
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)


# ---------------------------------------------------------------------------
# 1) Hijack sys.modules BEFORE production celery imports anything.
# ---------------------------------------------------------------------------

import tests.e2e.fakes.composio_module as _fake_composio  # noqa: E402
import tests.e2e.fakes.notion_module as _fake_notion  # noqa: E402

sys.modules["composio"] = _fake_composio
sys.modules["notion_client"] = _fake_notion
sys.modules["notion_client.errors"] = _fake_notion.errors


# ---------------------------------------------------------------------------
# 2) Logging + dotenv.
# ---------------------------------------------------------------------------

from dotenv import load_dotenv  # noqa: E402

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
# Native Google OAuth — fake Flow in tests.e2e.fakes.native_google raises
# "Fake Google Flow requires redirect_uri." when these are empty.
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("surfsense.e2e.celery")
logger.warning("*** SURFSENSE E2E CELERY WORKER — fake Composio + LLM + embeddings ***")


# ---------------------------------------------------------------------------
# 2.5) Materialise the synthetic global_llm_config.yaml so the worker's
#      view of app.config.GLOBAL_LLM_CONFIGS matches the API container.
#      Must run BEFORE the production celery_app import below, which
#      transitively imports app.config. Install-only-if-missing so a
#      developer's local config (with real API keys) is preserved.
# ---------------------------------------------------------------------------
import shutil as _shutil  # noqa: E402

_e2e_llm_cfg_src = os.path.join(_THIS_DIR, "fixtures", "global_llm_config.yaml")
_e2e_llm_cfg_dst = os.path.join(
    _BACKEND_ROOT, "app", "config", "global_llm_config.yaml"
)
if not os.path.exists(_e2e_llm_cfg_src):
    raise RuntimeError(
        f"E2E synthetic global LLM config fixture missing at {_e2e_llm_cfg_src!r}. "
        f"Restore tests/e2e/fixtures/global_llm_config.yaml from VCS."
    )
if os.path.exists(_e2e_llm_cfg_dst):
    logger.info(
        "[e2e-global-llm-config] %s already exists; leaving it alone "
        "(local dev config preserved)",
        _e2e_llm_cfg_dst,
    )
else:
    os.makedirs(os.path.dirname(_e2e_llm_cfg_dst), exist_ok=True)
    _shutil.copyfile(_e2e_llm_cfg_src, _e2e_llm_cfg_dst)
    logger.info(
        "[e2e-global-llm-config] installed %s -> %s",
        _e2e_llm_cfg_src,
        _e2e_llm_cfg_dst,
    )


# ---------------------------------------------------------------------------
# 3) Import the production celery_app. All task modules load here.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 4) Patch LLM + embedding bindings inside the worker process.
# ---------------------------------------------------------------------------
from unittest.mock import patch  # noqa: E402

from app.celery_app import celery_app  # noqa: E402
from tests.e2e.fakes import (  # noqa: E402
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
from tests.e2e.fakes.chat_llm import (  # noqa: E402
    fake_create_chat_litellm_from_agent_config,
    fake_create_chat_litellm_from_config,
)
from tests.e2e.fakes.llm import fake_get_user_long_context_llm  # noqa: E402

_active_patches: list = []


def _patch_llm_bindings() -> None:
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
            logger.info("[fake-llm] patched %s in celery worker", target)
        except (ModuleNotFoundError, AttributeError) as exc:
            logger.warning(
                "[fake-llm] could not patch %s in celery worker: %s.",
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
            logger.info("[fake-chat-llm] patched %s in celery worker", target)
        except (ModuleNotFoundError, AttributeError) as exc:
            logger.warning(
                "[fake-chat-llm] could not patch %s in celery worker: %s.",
                target,
                exc,
            )


_patch_llm_bindings()
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


# ---------------------------------------------------------------------------
# 5) Start the worker.
# ---------------------------------------------------------------------------


def _main() -> None:
    # Default queues mirror production (default queue + connectors queue
    # so Drive indexing tasks are picked up).
    queue_name = os.getenv("CELERY_TASK_DEFAULT_QUEUE", "surfsense")
    queues = f"{queue_name},{queue_name}.connectors"

    # macOS forks-after-MPS-init crash prefork workers; threads avoid it.
    default_pool = "threads" if sys.platform == "darwin" else "prefork"
    pool = os.getenv("CELERY_POOL", default_pool)
    concurrency = os.getenv("CELERY_CONCURRENCY", "2")

    celery_app.worker_main(
        argv=[
            "worker",
            "--loglevel=info",
            f"--queues={queues}",
            f"--pool={pool}",
            f"--concurrency={concurrency}",
            "--without-gossip",
            "--without-mingle",
        ]
    )


if __name__ == "__main__":
    _main()
