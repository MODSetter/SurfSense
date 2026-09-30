"""The process table's parent links, from psutil's one-snapshot map."""

import os

import psutil
import pytest

from modules.resource_usage.parent_map import parent_map

pytestmark = pytest.mark.unit


def test_psutil_still_exports_the_snapshot_it_builds_children_on() -> None:
    """Private upstream. The fallback answers the same but costs ten times as
    much on every poll, so a psutil bump that drops it should fail here."""
    assert callable(getattr(psutil, "_ppid_map", None))


def test_this_process_is_listed_under_its_parent() -> None:
    """The map holds real parent links, whichever path produced it."""
    assert parent_map()[os.getpid()] == os.getppid()
