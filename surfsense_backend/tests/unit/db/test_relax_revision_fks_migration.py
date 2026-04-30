"""Smoke test for the ``134_relax_revision_fks`` Alembic migration.

A full apply/rollback test would require a live Postgres; here we verify
the migration module's static contract:

* The chain wires it as a successor of ``133_drop_documents_content_hash_unique``.
* ``upgrade()`` declares two FK creations with ``ondelete='SET NULL'``
  (one for ``document_revisions.document_id``, one for
  ``folder_revisions.folder_id``).
* ``downgrade()`` re-establishes ``ondelete='CASCADE'`` after draining
  orphaned revisions.

If any of these invariants regress the snapshot/revert pipeline silently
loses the ability to undo ``rm`` / ``rmdir`` on environments that ran the
migration "down" or never ran it at all.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "134_relax_revision_fks.py"
)


def _load_migration():
    """Load the migration module by file path (no package import needed)."""
    spec = importlib.util.spec_from_file_location("_migration_134", _MIGRATION_PATH)
    assert spec and spec.loader, "could not load migration spec"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_chain_revision_ids() -> None:
    module = _load_migration()
    # The migration file uses short numeric revision IDs to match the
    # in-tree convention (cf. ``133`` -> ``134``); the ``134_<slug>.py``
    # filename is documentation, not the canonical revision string.
    assert getattr(module, "revision", None) == "134"
    assert getattr(module, "down_revision", None) == "133"


def test_migration_exposes_upgrade_and_downgrade() -> None:
    module = _load_migration()
    upgrade = getattr(module, "upgrade", None)
    downgrade = getattr(module, "downgrade", None)
    assert callable(upgrade), "upgrade() is required"
    assert callable(downgrade), "downgrade() is required"


def test_upgrade_creates_set_null_fks_for_both_revision_tables() -> None:
    module = _load_migration()
    src = inspect.getsource(module.upgrade)
    assert "document_revisions" in src
    assert "folder_revisions" in src
    # Both new FKs MUST be ON DELETE SET NULL — that's the entire point
    # of the migration: snapshots must outlive their parent row.
    assert src.count('ondelete="SET NULL"') >= 2
    # And the ``document_id`` / ``folder_id`` columns become nullable.
    assert "nullable=True" in src


def test_downgrade_drains_orphans_then_restores_cascade() -> None:
    module = _load_migration()
    src = inspect.getsource(module.downgrade)
    # Drain orphaned rows BEFORE we can re-impose NOT NULL.
    assert "DELETE FROM document_revisions WHERE document_id IS NULL" in src
    assert "DELETE FROM folder_revisions WHERE folder_id IS NULL" in src
    # Then restore the original CASCADE/NOT NULL contract.
    assert src.count('ondelete="CASCADE"') >= 2
    assert "nullable=False" in src
