"""What ``read_file`` promises the model must match what it returns.

The description is the model's only account of the read format, and only
cloud-on-Postgres actually renders a citation envelope. Promising `[n]` labels
where none appear is not a missing citation but a wrong one: the ordinals in
context belong to ``search_knowledge_base``, and a model told to reuse them can
credit a search result for text it read out of a file.
"""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode
from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.tools.read_file.description import (
    select_description,
)

pytestmark = pytest.mark.unit

_ENVELOPE_PROMISE = 'view="full"'


def test_cloud_on_postgres_is_told_about_the_citation_envelope() -> None:
    """The one mode that renders `<document>` blocks with `[n]` passages."""
    description = select_description(FilesystemMode.CLOUD, git_native=False)

    assert _ENVELOPE_PROMISE in description
    assert "Cite a passage by writing its `[n]`" in description


@pytest.mark.parametrize(
    ("mode", "git_native"),
    [
        (FilesystemMode.CLOUD, True),
        (FilesystemMode.DESKTOP_LOCAL_FOLDER, False),
        (FilesystemMode.DESKTOP_LOCAL_FOLDER, True),
    ],
    ids=["git-native", "desktop", "desktop-with-flag-set"],
)
def test_raw_reads_are_never_promised_labels_they_do_not_carry(
    mode: FilesystemMode, git_native: bool
) -> None:
    """Git-native and desktop both return the file's own bytes, unlabelled.

    Desktop is included because it had the same wrong description before the
    flag existed — the split is by read format, not by cloud-vs-desktop.
    """
    description = select_description(mode, git_native=git_native)

    assert _ENVELOPE_PROMISE not in description
    assert "with no `[n]` labels" in description


def test_raw_reads_forbid_reusing_a_search_ordinal() -> None:
    """The mis-citation this guard exists to prevent, named explicitly."""
    description = select_description(FilesystemMode.CLOUD, git_native=True)

    assert "Never attach an `[n]` to a statement taken from a read" in description


def test_every_mode_still_documents_pagination_and_line_numbers() -> None:
    """Splitting the description must not drop what both variants share."""
    for description in (
        select_description(FilesystemMode.CLOUD, git_native=False),
        select_description(FilesystemMode.CLOUD, git_native=True),
    ):
        assert "`offset` and `limit`" in description
        assert "Results include line numbers." in description
