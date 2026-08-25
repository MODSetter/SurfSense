"""Guard: integration tests must never write to the real KB store root.

A test that writes to the default ``KNOWLEDGE_STORE_ROOT`` overwrites the dev
workspace repo with the same id (the test schema recycles low ids), which has
silently clobbered local data. The session-autouse fixture in ``conftest``
redirects the root under pytest's basetemp; this asserts it took.
"""

import pytest

from app.config import config as app_config

pytestmark = pytest.mark.integration


def test_store_root_is_redirected_under_pytest_tmp(tmp_path_factory):
    assert app_config.KNOWLEDGE_STORE_ROOT.startswith(
        str(tmp_path_factory.getbasetemp())
    )
