"""Where each source's text sits in a thread's `sources/`: the user's folders, made safe."""

from pathlib import PurePosixPath, PureWindowsPath

import pytest

from modules.agent.thread_folder.mirror_path import (
    LiveFolder,
    MirroredSource,
    lay_out,
)

pytestmark = pytest.mark.unit

BASE = "C:/Users/me/.surfsense/data/workspaces/1/agent/threads/7/sources"
LIBRARY = LiveFolder(1, None, "Library")


def _paths(
    docs: list[MirroredSource], folders: list[LiveFolder], base: str = BASE
) -> dict[int, str]:
    return {i: p.as_posix() for i, p in lay_out(base, docs, folders).items()}


def _in_folder(name: str, folder_id: int = 2) -> str:
    """The directory a single Library subfolder of that name lands in."""
    folders = [LIBRARY, LiveFolder(folder_id, 1, name)]
    path = _paths([MirroredSource(9, "Plan", folder_id)], folders)[9]
    return PurePosixPath(path).parent.name


def test_a_filed_source_sits_under_its_root_and_folders() -> None:
    """The agent finds a source where the user filed it."""
    folders = [LIBRARY, LiveFolder(2, 1, "Research"), LiveFolder(3, 2, "2026")]
    docs = [
        MirroredSource(5, "Q3 report.pdf", 3),
        MirroredSource(6, "Plan", 1),
        MirroredSource(7, "Quiz", None),
    ]

    assert _paths(docs, folders) == {
        5: "Library/Research/2026/Q3 report.pdf [5].md",
        6: "Library/Plan [6].md",
        # An unfiled artifact ticked by id has no folder: it sits at the top.
        7: "Quiz [7].md",
    }


@pytest.mark.parametrize(
    ("name", "becomes"),
    [
        ("a:b", "a_b"),
        ("a?b", "a_b"),
        (".hidden", "hidden"),
        ("..", "untitled"),
        ("  .  ", "untitled"),
        ("x" * 150, "x" * 100),
    ],
)
def test_a_folder_name_is_made_safe_and_visible(name: str, becomes: str) -> None:
    """A leading dot would hide the folder from grep and glob, which skip hidden entries."""
    assert _in_folder(name) == becomes


@pytest.mark.parametrize(
    ("name", "becomes"),
    [
        ("CON", "CON_"),
        ("CON .txt", "CON_ .txt"),
        ("com1.txt", "com1_.txt"),
        ("COM¹", "COM¹_"),
        ("CONIN$", "CONIN$_"),
        ("lpt9", "lpt9_"),
        ("agents.md", "agents.md_"),
        ("CLAUDE.md", "CLAUDE.md_"),
        ("Context.md", "Context.md_"),
        ("console", "console"),
    ],
)
def test_a_name_windows_or_opencode_reads_specially_gains_an_underscore(
    name: str, becomes: str
) -> None:
    """A device name cannot be a folder on Windows; an instruction file's name would be read as one."""
    assert _in_folder(name) == becomes


def test_figures_and_pages_are_kept_for_surfsense_at_the_top() -> None:
    """Shown figures and drawn pages live in `sources/figures` and `sources/pages`."""
    folders = [LiveFolder(1, None, "figures"), LiveFolder(2, 1, "pages")]

    path = _paths([MirroredSource(9, "Plan", 2)], folders)[9]

    assert path == "figures_/pages/Plan [9].md"


def test_names_equal_once_made_safe_each_get_their_folder_id() -> None:
    """Two folders must never share one directory."""
    folders = [LIBRARY, LiveFolder(2, 1, "a:b"), LiveFolder(3, 1, "A?B")]
    docs = [MirroredSource(5, "x", 2), MirroredSource(6, "y", 3)]

    assert _paths(docs, folders) == {
        5: "Library/a_b [f2]/x [5].md",
        6: "Library/A_B [f3]/y [6].md",
    }


@pytest.mark.parametrize("name", ["x [f3]", "y [5].md"])
def test_a_name_that_mimics_a_suffix_gets_one_of_its_own(name: str) -> None:
    """Otherwise it could pass for another folder, or for a source's file."""
    assert _in_folder(name, folder_id=4) == f"{name} [f4]"


def _deep_chain(depth: int, name_length: int) -> list[LiveFolder]:
    folders = [LIBRARY]
    for n in range(depth):
        folders.append(LiveFolder(n + 2, n + 1, chr(ord("a") + n) * name_length))
    return folders


def test_a_deep_chain_under_a_long_base_fits_windows_paths() -> None:
    """Every file fits MAX_PATH and every directory CreateDirectory's limit."""
    base = "C:/" + "b" * 117
    folders = _deep_chain(12, 40)
    docs = [MirroredSource(n, "t" * 90, folders[n].id) for n in range(1, 13)]

    paths = lay_out(base, docs, folders)

    assert set(paths) == set(range(1, 13))
    for n, path in paths.items():
        assert len(str(PureWindowsPath(base) / path)) <= 259
        assert len(str(PureWindowsPath(base) / path.parent)) <= 247
        assert path.name.endswith(f" [{n}].md")


def test_two_titles_of_different_lengths_in_one_deep_folder_share_its_directory() -> (
    None
):
    """The cuts are the folders', so one folder never splits into two directories."""
    base = "C:/" + "b" * 117
    folders = _deep_chain(6, 40)
    deepest = folders[-1].id
    docs = [MirroredSource(5, "t" * 90, deepest), MirroredSource(6, "short", deepest)]

    paths = lay_out(base, docs, folders)

    assert paths[5].parent == paths[6].parent
    assert len(paths[5].parent.parts) == 7
    assert len(str(PureWindowsPath(base) / paths[5])) <= 259


def test_each_folder_of_a_chain_keeps_one_directory_for_all_its_files() -> None:
    """A folder's cut is the folder's, whatever its files' titles."""
    base = "C:/" + "b" * 117
    folders = _deep_chain(6, 40)
    docs = [MirroredSource(n, "t" * (15 * n), folders[n].id) for n in range(1, 7)]

    paths = lay_out(base, docs, folders)

    for n in range(1, 6):
        assert paths[n].parent == paths[n + 1].parent.parent


def test_a_title_too_long_for_its_folder_is_cut_and_keeps_its_id() -> None:
    """The id stays: citations, create_artifact and the note read it."""
    base = "C:/" + "b" * 200
    folders = [LIBRARY, LiveFolder(2, 1, "Research")]

    (path,) = lay_out(base, [MirroredSource(5, "t" * 100, 2)], folders).values()

    assert len(str(PureWindowsPath(base) / path)) <= 259
    assert path.name.endswith(" [5].md")
    assert path.parent.as_posix() == "Library/Research"


def test_a_source_whose_folder_cannot_fit_goes_flat() -> None:
    """With every folder already cut, only the top of `sources/` is short enough."""
    base = "C:/" + "b" * 225
    folders = _deep_chain(4, 20)

    (path,) = lay_out(
        base, [MirroredSource(5, "Plan", folders[-1].id)], folders
    ).values()

    assert path.as_posix() == "Plan [5].md"


def test_a_source_that_cannot_fit_even_flat_is_left_out() -> None:
    """Search still labels it; there is no file to open."""
    base = "C:/" + "b" * 250

    assert lay_out(base, [MirroredSource(12345, "Plan", None)], []) == {}


def test_unticking_a_sibling_moves_no_path() -> None:
    """Every decision reads the workspace's folders and the source itself, never the scope."""
    folders = [LIBRARY, LiveFolder(2, 1, "a:b"), LiveFolder(3, 1, "a?b")]
    both = [MirroredSource(5, "x", 2), MirroredSource(6, "y", 3)]

    assert _paths(both[:1], folders) == {5: _paths(both, folders)[5]}


def test_a_title_cannot_leave_the_folder() -> None:
    """A title and a folder name are user text; no part may climb out."""
    folders = [LIBRARY, LiveFolder(2, 1, "../..")]

    (path,) = lay_out(BASE, [MirroredSource(5, "../../x", 2)], folders).values()

    assert ".." not in path.parts
    assert all("/" not in part and "\\" not in part for part in path.parts)


def test_an_unfiled_source_keeps_as_much_title_as_the_top_has_room_for() -> None:
    """Flat is its place, not a fallback: the title is cut only as far as it must be."""
    base = "C:/" + "b" * 237

    (path,) = lay_out(base, [MirroredSource(1, "Plan 2026 report", None)], []).values()

    assert path.as_posix() == "Plan 2026 r [1].md"


@pytest.mark.parametrize("name", ["outputs", "Outputs", "OUTPUTS.", "output\u017f"])
def test_no_folder_passes_for_the_agents_outputs(name: str) -> None:
    """The edit rules allow any path holding `/outputs/` past a thread's folder.

    On macOS they match case as written while the disk ignores it, so
    `Sources/…/outputs/x.md` would miss the `sources/` deny and write through a
    view into every thread's text.
    """
    folders = [LiveFolder(1, None, name), LiveFolder(2, 1, name)]

    (path,) = lay_out(BASE, [MirroredSource(9, "Plan", 2)], folders).values()

    assert all(part.casefold() != "outputs" for part in path.parts), path


def test_a_path_is_measured_as_windows_measures_it_in_utf_16_units() -> None:
    """An emoji is one character to Python and two to MAX_PATH."""
    base = "C:/" + "b" * 200

    path = _paths([MirroredSource(9, "😀" * 60, None)], [], base)[9]

    whole = f"{base}/{path}"
    assert len(whole.encode("utf-16-le")) // 2 <= 259
    assert path.startswith("😀")


def test_a_folder_is_measured_in_utf_16_units_too() -> None:
    """A folder of emoji that fits by characters but not by units is cut."""
    base = "C:/" + "b" * 150
    folders = [LiveFolder(1, None, "😀" * 60)]

    path = _paths([MirroredSource(9, "Plan", 1)], folders, base)[9]

    assert len(f"{base}/{path}".encode("utf-16-le")) // 2 <= 259
