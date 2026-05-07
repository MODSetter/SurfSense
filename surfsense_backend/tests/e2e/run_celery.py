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
os.environ.setdefault("NOTION_CLIENT_ID", "fake-notion-client-id")
os.environ.setdefault("NOTION_CLIENT_SECRET", "fake-notion-client-secret")
os.environ.setdefault(
    "NOTION_REDIRECT_URI",
    "http://localhost:8000/api/v1/auth/notion/connector/callback",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("surfsense.e2e.celery")
logger.warning(
    "*** SURFSENSE E2E CELERY WORKER — fake Composio + LLM + embeddings, "
    "this MUST NOT be reachable in production. ***"
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
    embeddings as _fake_embeddings,
    native_google as _fake_native_google,
    notion_module as _fake_notion_module,
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
        "app.tasks.connector_indexers.google_drive_indexer.get_user_long_context_llm",
        "app.tasks.connector_indexers.google_gmail_indexer.get_user_long_context_llm",
        "app.tasks.connector_indexers.notion_indexer.get_user_long_context_llm",
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
_fake_native_google.install(_active_patches)
_fake_notion_module.install(_active_patches)


# ---------------------------------------------------------------------------
# 5) Start the worker.
# ---------------------------------------------------------------------------


def _main() -> None:
    # Default queues mirror production (default queue + connectors queue
    # so Drive indexing tasks are picked up).
    queue_name = os.getenv("CELERY_TASK_DEFAULT_QUEUE", "surfsense")
    queues = f"{queue_name},{queue_name}.connectors"
    celery_app.worker_main(
        argv=[
            "worker",
            "--loglevel=info",
            f"--queues={queues}",
            "--concurrency=2",
            "--without-gossip",
            "--without-mingle",
        ]
    )


if __name__ == "__main__":
    _main()
