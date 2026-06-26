"""Tests for folder pointer-path shaping."""

from __future__ import annotations

import pytest

from app.agents.chat.runtime.references.folders import folder_pointer_path

pytestmark = pytest.mark.unit


def test_adds_trailing_slash_so_path_reads_as_directory() -> None:
    assert folder_pointer_path(7, {7: "/documents/Specs"}) == "/documents/Specs/"


def test_keeps_existing_trailing_slash() -> None:
    assert folder_pointer_path(7, {7: "/documents/Specs/"}) == "/documents/Specs/"


def test_unknown_folder_falls_back_to_documents_root() -> None:
    assert folder_pointer_path(99, {}) == "/documents/"
