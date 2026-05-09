from tests.e2e.fakes.composio_module import _drive_list_files


def _ids(result: dict) -> set[str]:
    return {item["id"] for item in result["data"]["files"]}


def test_drive_list_files_filters_shortcuts_and_trashed_items():
    result = _drive_list_files(
        {
            "q": (
                "'root' in parents and trashed = false and "
                "mimeType != 'application/vnd.google-apps.shortcut'"
            )
        }
    )

    ids = _ids(result)

    assert "fake-file-canary" in ids
    assert "fake-shortcut-canary" not in ids
    assert "fake-file-trashed" not in ids


def test_drive_list_files_filters_to_exact_mime_type():
    result = _drive_list_files(
        {"q": "'root' in parents and trashed = false and mimeType = 'text/plain'"}
    )

    assert _ids(result) == {"fake-file-canary"}


def test_drive_list_files_uses_requested_parent_folder():
    result = _drive_list_files(
        {"q": "'fake-folder-projects' in parents and trashed = false"}
    )

    assert _ids(result) == {"fake-file-roadmap"}
