"""A zipped pack installs only when every member is a plain file, at a name every system the app
runs on can write, within the caps; a zip that cannot be read is no pack, never a crash.

Contract 6's zip section is one set of rules for the app and the license server, checked on
the zip's own list, the same on every system, before anything is written."""

import errno
import hashlib
import json
import os
import sys
import tracemalloc
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from modules.jobs.packs.install import install_pack
from modules.jobs.packs.installed import installed_packs
from modules.jobs.packs.integrity import MAX_PACK_BYTES
from modules.jobs.packs.manifest import MANIFEST, PackRefusedError, safe_path
from tests.job_pack_samples import PACK_ID, sign_pack, write_questionnaire_pack
from tests.zip_faults import corrupted, encrypted

pytestmark = pytest.mark.unit

# A zip member: its name, or its own entry for a folder, and the bytes it holds.
Member = tuple[str | zipfile.ZipInfo, bytes]
# The test pack's own members: its manifest and signature, and the seven files it lists.
PACK_MEMBERS = 9


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    """A sealed pack folder SurfSense's test key signed."""
    return write_questionnaire_pack(tmp_path / "pack")


@pytest.fixture
def written(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Each file an install asks the system to write in its scratch folder, by its name in the
    pack. A zip the rules refuse asks for none, so no system's own answer decides."""
    names: list[str] = []
    real_open = Path.open

    def open_watched(self: Path, mode: str = "r", *args: object, **kwargs: object):
        scratch = [
            n for n, part in enumerate(self.parts) if part.startswith(".installing-")
        ]
        if "w" in mode and scratch:
            names.append("/".join(self.parts[scratch[0] + 2 :]))
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_watched)
    return names


def folder_entry(name: str) -> zipfile.ZipInfo:
    """A zip's own entry for a folder, as many tools write one."""
    return zipfile.ZipInfo(name, date_time=(2026, 11, 3, 0, 0, 0))


def stored_as(name: str) -> zipfile.ZipInfo:
    """An entry stored under exactly `name`, as a zip made elsewhere holds it: ZipInfo would
    cut a NUL and, on Windows, turn a backslash into a slash."""
    entry = zipfile.ZipInfo("member", date_time=(2026, 11, 3, 0, 0, 0))
    entry.filename = name
    return entry


def listed(pack: Path, *members: Member) -> Callable[[zipfile.ZipFile], None]:
    """Lists each file of `members` in the pack's manifest, signed again, and gives what writes
    them into the zip, so only their names can be at fault."""
    path = pack / MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for name, data in members:
        if isinstance(name, str):
            manifest["files"][name] = hashlib.sha256(data).hexdigest()
    path.write_text(json.dumps(manifest), encoding="utf-8")
    sign_pack(pack)
    return lambda archive: added(archive, *members)


def added(archive: zipfile.ZipFile, *members: Member) -> None:
    """Write each of `members` into the zip, files and folder entries alike."""
    for name, data in members:
        archive.writestr(name, data)


def zipped(
    pack: Path,
    out: Path,
    *,
    compression: int = zipfile.ZIP_DEFLATED,
    wrap: str = "",
    add: Callable[[zipfile.ZipFile], None] | None = None,
) -> Path:
    """The pack's files as a zip, each under `wrap`, with whatever `add` writes besides."""
    with zipfile.ZipFile(out, "w", compression) as archive:
        for path in sorted(p for p in pack.rglob("*") if p.is_file()):
            archive.write(path, wrap + path.relative_to(pack).as_posix())
        if add is not None:
            add(archive)
    return out


def refused(archive: Path, root: Path) -> str:
    """The code the install refuses `archive` with; nothing is installed."""
    return refusal_of(archive, root).code


def refusal_of(archive: Path, root: Path) -> PackRefusedError:
    """The install's refusal of `archive`; nothing is installed."""
    with pytest.raises(PackRefusedError) as refusal:
        install_pack(archive, root)
    assert installed_packs(root) == []
    return refusal.value


@pytest.mark.parametrize("wrap", ["", f"{PACK_ID}/"])
def test_a_zip_with_or_without_a_wrapping_folder_installs(
    pack: Path, tmp_path: Path, wrap: str
) -> None:
    """A zip made by hand often wraps the pack in its folder; the folder is taken off."""
    archive = zipped(pack, tmp_path / "pack.zip", wrap=wrap)

    assert install_pack(archive, tmp_path / "installed").id == PACK_ID


def test_more_than_a_thousand_members_is_not_a_pack(pack: Path, tmp_path: Path) -> None:
    """The member count is capped before anything is extracted. No pack holds that many
    files, so a small zip of them is some other archive, not one too large."""

    def a_thousand_more(archive: zipfile.ZipFile) -> None:
        for n in range(1000):
            archive.writestr(f"extra/{n}.md", "x")

    archive = zipped(pack, tmp_path / "many.zip", add=a_thousand_more)

    assert refused(archive, tmp_path / "installed") == "NOT_A_PACK"


@pytest.mark.parametrize(
    ("folders", "installs"),
    [(1000 - PACK_MEMBERS, True), (1001 - PACK_MEMBERS, False)],
    ids=["1,000 members", "1,001 members"],
)
def test_folder_entries_count_toward_the_thousand_members(
    pack: Path, tmp_path: Path, written: list[str], folders: int, installs: bool
) -> None:
    """Contract 6 bounds the members, folders among them, as the license server counts them:
    a pack and its folder entries up to 1,000 install, and one more is no pack, refused
    before any file is written."""
    entries = [(folder_entry(f"jobs/{n}/"), b"") for n in range(folders)]
    archive = zipped(pack, tmp_path / "folders.zip", add=lambda a: added(a, *entries))

    if installs:
        assert install_pack(archive, tmp_path / "installed").id == PACK_ID
    else:
        assert refused(archive, tmp_path / "installed") == "NOT_A_PACK"
        assert written == []


def test_a_name_thousands_of_folders_deep_is_refused_for_its_length_at_little_cost(
    pack: Path, tmp_path: Path, written: list[str]
) -> None:
    """The names are checked before the signature, so on a zip anyone can make. A name's
    length is checked before its folders are walked: every folder's whole name of a folder
    entry 5,000 folders deep would fill some 50 MiB, while the zip is refused in under
    8 MiB, before any file is written."""
    deep = (folder_entry("a/" * 5000), b"")
    archive = zipped(pack, tmp_path / "deep.zip", add=lambda a: added(a, deep))

    tracemalloc.start()
    try:
        code = refused(archive, tmp_path / "installed")
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert code == "BAD_PATH"
    assert written == []
    assert peak < 8 * 2**20, f"peak {peak / 2**20:.1f} MiB"


@pytest.mark.parametrize("wrap", ["", f"{PACK_ID}/"])
def test_folder_entries_that_carry_nothing_are_accepted(
    pack: Path, tmp_path: Path, wrap: str
) -> None:
    """A zip that names each folder, as many tools write one, installs with or without a
    folder wrapping the pack; the folders carry nothing."""
    folders = [
        f"{wrap}{path.relative_to(pack).as_posix()}/"
        for path in sorted(pack.rglob("*"))
        if path.is_dir()
    ]
    entries = [(folder_entry(name), b"") for name in [wrap, *folders] if name]
    archive = zipped(
        pack, tmp_path / "named.zip", wrap=wrap, add=lambda a: added(a, *entries)
    )

    assert install_pack(archive, tmp_path / "installed").id == PACK_ID


def test_a_folder_entry_carrying_data_is_not_a_pack(
    pack: Path, tmp_path: Path, written: list[str]
) -> None:
    """A folder carries nothing, so bytes in one would sit in the pack unlisted and
    unsigned."""
    entry = (folder_entry("jobs/"), b"x" * 1024)
    archive = zipped(pack, tmp_path / "laden.zip", add=lambda a: added(a, entry))

    assert refused(archive, tmp_path / "installed") == "NOT_A_PACK"
    assert written == []


@pytest.mark.parametrize(
    "name", ["nul", "com1.txt", "docs/AUX.md", "Lpt9", "notes.", "dir./x.md", "draft "]
)
def test_a_name_windows_cannot_write_is_a_bad_path(
    pack: Path, tmp_path: Path, name: str
) -> None:
    """A device's name, with or without an extension, or a part ending in a dot or a space,
    would be another file on Windows than the one the manifest lists."""
    archive = zipped(pack, tmp_path / "named.zip", add=lambda a: a.writestr(name, "x"))

    assert refused(archive, tmp_path / "installed") == "BAD_PATH"


@pytest.mark.parametrize(
    "names",
    [
        ("docs", "docs/notes.md"),
        ("docs/notes.md", "docs"),
        ("docs", "docs/a/notes.md"),
        ("docs/a/notes.md", "docs/a"),
    ],
    ids=[
        "file then child",
        "child then file",
        "file then grandchild",
        "grandchild then file",
    ],
)
def test_a_name_that_is_also_a_folder_of_the_zip_is_a_bad_path(
    pack: Path, tmp_path: Path, written: list[str], names: tuple[str, str]
) -> None:
    """No disk holds a file and a folder of one name, so the zip cannot hold what it lists:
    refused for its names, in either order, on every system before any file is written,
    never taken for a full disk."""
    archive = zipped(
        pack,
        tmp_path / "clash.zip",
        add=lambda a: added(a, *((n, b"x") for n in names)),
    )

    assert refused(archive, tmp_path / "installed") == "BAD_PATH"
    assert written == []


@pytest.mark.parametrize(
    "name",
    [
        "a?b.md",
        "a<b.md",
        "a>b.md",
        "a|b.md",
        'a"b.md',
        "a*b.md",
        "a\x01b.md",
        "a\tb.md",
        "docs/a\x1f.md",
        "x?y/z.md",
    ],
)
def test_a_name_windows_cannot_hold_is_a_bad_path_on_every_system(
    pack: Path, tmp_path: Path, written: list[str], name: str
) -> None:
    """Windows holds none of these characters in a name, as a zip made elsewhere may: the
    zip is refused for its name on every system, before any file is written, and never
    taken for a full disk."""
    archive = zipped(pack, tmp_path / "named.zip", add=lambda a: a.writestr(name, "x"))

    assert refused(archive, tmp_path / "installed") == "BAD_PATH"
    assert written == []


def test_a_name_no_disk_can_hold_is_still_the_zip_s_fault(
    pack: Path, tmp_path: Path, written: list[str]
) -> None:
    """A part longer than any disk holds is refused for its length, as the license server
    words it, before any file is written: never taken for a full disk."""
    name = f"docs/{'x' * 300}.md"
    archive = zipped(pack, tmp_path / "long.zip", add=lambda a: a.writestr(name, "x"))

    refusal = refusal_of(archive, tmp_path / "installed")

    assert (refusal.code, refusal.message) == (
        "BAD_PATH",
        f"{name[:60]!r}... is longer than 255 bytes in UTF-8.",
    )
    assert written == []


def test_a_name_this_disk_refuses_once_the_rules_pass_is_still_the_zip_s_fault(
    pack: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What else a system refuses as a name once every rule passes, as a path too long for
    Windows without long paths, is the zip's fault too, found as it is written: never taken
    for a full disk."""
    name = "docs/notes.md"
    archive = zipped(pack, tmp_path / "named.zip", add=listed(pack, (name, b"x")))
    real_open = Path.open

    def open_or_refuse(self: Path, mode: str = "r", *args: object, **kwargs: object):
        staged = ".installing-" in self.as_posix()
        if "w" in mode and staged and self.as_posix().endswith(f"/{name}"):
            raise OSError(
                errno.ENAMETOOLONG, os.strerror(errno.ENAMETOOLONG), str(self)
            )
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_or_refuse)

    refusal = refusal_of(archive, tmp_path / "installed")

    assert (refusal.code, refusal.message) == (
        "BAD_PATH",
        f"{name!r} cannot be written as a file on this computer.",
    )


@pytest.mark.parametrize(
    "members",
    [
        pytest.param((("jobs/q?.json", b"x"),), id="a question mark"),
        pytest.param((("a*b", b"x"),), id="an asterisk"),
        pytest.param((('a"b', b"x"),), id="a double quote"),
        pytest.param((("a<b", b"x"),), id="a less-than sign"),
        pytest.param((("a>b", b"x"),), id="a greater-than sign"),
        pytest.param((("a|b", b"x"),), id="a pipe"),
        pytest.param((("a\x01b", b"x"),), id="a control character"),
        pytest.param((("docs/a\x1f", b"x"),), id="the last control character"),
        pytest.param(
            (("notes", b"x"), ("notes/a.txt", b"y")), id="a file that is also a folder"
        ),
        pytest.param(
            (("notes/a.txt", b"y"), ("notes", b"x")), id="a folder that is also a file"
        ),
        pytest.param(
            (("notes", b"x"), (folder_entry("notes/"), b"")),
            id="a file beside a folder entry of its name",
        ),
        pytest.param(
            ((folder_entry("notes/"), b""), ("notes", b"x")),
            id="a folder entry beside a file of its name",
        ),
        pytest.param(
            (("Notes", b"x"), ("notes/a.txt", b"y")),
            id="a file that is a folder but for case",
        ),
        pytest.param(
            (("Docs/a.txt", b"a"), ("docs/b.txt", b"b")),
            id="a folder spelled two ways",
        ),
        pytest.param(
            ((folder_entry("Jobs/"), b""),),
            id="a folder entry spelled unlike its files",
        ),
        pytest.param(((".", b"x"),), id="a lone dot"),
        pytest.param(((folder_entry("./"), b""),), id="a folder entry of a lone dot"),
        pytest.param(
            (("0123456789.md", b"one"), ("012345~1.MD", b"two")),
            id="the short name of another file",
        ),
        pytest.param(
            (("0123456789/a.md", b"a"), ("012345~1/b.md", b"b")),
            id="the short name of another folder",
        ),
        pytest.param((("docs/REPORT~12", b"x"),), id="a short name, no extension"),
    ],
)
def test_a_listed_name_windows_could_not_extract_as_named_is_a_bad_path(
    pack: Path, tmp_path: Path, written: list[str], members: tuple[Member, ...]
) -> None:
    """The license server's own cases: each listed in the manifest, so only its name is at
    fault. Some systems would write it and others fail it or file it under another name, as
    Windows opens the file a short name stands for, so every system refuses it, before any
    file is written."""
    archive = zipped(pack, tmp_path / "listed.zip", add=listed(pack, *members))

    assert refused(archive, tmp_path / "installed") == "BAD_PATH"
    assert written == []


EDGE_MEMBERS = (
    ("docs/" + "x" * 250, b"a"),
    ("é" * 127 + "x", b"b"),
    ("notes~v2.md", b"c"),
    ("archive~1.tar.gz", b"d"),
)


def _writes_paths_past_260_characters() -> bool:
    """Every system but Windows with long paths off, which caps a whole path at 260."""
    if sys.platform != "win32":
        return True
    import ctypes

    enabled = ctypes.WinDLL("ntdll").RtlAreLongPathsEnabled
    enabled.restype = ctypes.c_ubyte
    return bool(enabled())


def test_names_at_the_rules_edges_pass_the_name_rules() -> None:
    """255 bytes in UTF-8, and a tilde that no Windows short name could end in, on every
    system: no disk is asked."""
    assert [safe_path(name).as_posix() for name, _ in EDGE_MEMBERS] == [
        name for name, _ in EDGE_MEMBERS
    ]


@pytest.mark.skipif(
    not _writes_paths_past_260_characters(),
    reason="Windows with long paths off caps a whole path at 260 characters, and a "
    "255-byte name in the test's folder makes a longer one",
)
def test_names_at_the_rules_edges_are_accepted(pack: Path, tmp_path: Path) -> None:
    """Each listed and written, so the pack installs with them."""
    members = EDGE_MEMBERS
    archive = zipped(pack, tmp_path / "edges.zip", add=listed(pack, *members))

    installed = install_pack(archive, tmp_path / "installed")

    folder = tmp_path / "installed" / installed.id / installed.version
    assert [(folder / name).read_bytes() for name, _ in members] == [
        data for _, data in members
    ]


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("docs/" + "x" * 251, id="256 bytes"),
        pytest.param("é" * 128, id="128 characters, 256 bytes in UTF-8"),
        pytest.param("docs/" + "x" * 300 + ".md", id="a part of 303 bytes"),
        # Its folders, not its bytes, cost the tree's check: the length comes first.
        pytest.param("a/" * 5000 + "x", id="5,000 folders deep"),
    ],
)
def test_a_name_past_255_bytes_is_a_bad_path(
    pack: Path, tmp_path: Path, written: list[str], name: str
) -> None:
    """No disk holds a name part past 255 bytes, and a longer name costs its checks more:
    the license server's cases, refused before any file is written."""
    archive = zipped(pack, tmp_path / "long.zip", add=listed(pack, (name, b"x")))

    assert refused(archive, tmp_path / "installed") == "BAD_PATH"
    assert written == []


def test_a_listed_path_past_255_bytes_is_a_bad_path_though_no_member_has_it(
    pack: Path, tmp_path: Path
) -> None:
    """The manifest's paths are held to the zip's rule for names, so a path no member has is
    refused for its length, not taken for a missing file."""
    listed(pack, ("docs/" + "x" * 251, b"x"))
    archive = zipped(pack, tmp_path / "listed.zip")

    assert refused(archive, tmp_path / "installed") == "BAD_PATH"


def test_a_listed_file_the_zip_holds_only_under_another_case_is_missing(
    pack: Path, tmp_path: Path
) -> None:
    """Whether a listed file is there is read from the pack's own names, so a disk that
    ignores case, as Windows and macOS do, answers as any other: the license server's
    answer on every system."""
    path = pack / MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    name = next(n for n in manifest["files"] if n.swapcase() != n)
    manifest["files"][name.swapcase()] = manifest["files"][name]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    sign_pack(pack)
    archive = zipped(pack, tmp_path / "case.zip")

    refusal = refusal_of(archive, tmp_path / "installed")

    assert (refusal.code, refusal.message) == (
        "PACK_FILE_MISSING",
        f"{name.swapcase()} is missing from the pack.",
    )


@pytest.mark.parametrize(
    ("stored", "read_as", "sentence"),
    [
        pytest.param("a\\b", "a/b", "is not a path inside the pack.", id="a backslash"),
        pytest.param(
            "a//b", "a/b", "is not a path inside the pack.", id="an empty part"
        ),
        pytest.param("a/./b", "a/b", "is not a path inside the pack.", id="a dot part"),
        pytest.param(
            "./a", "a", "is not a path inside the pack.", id="a leading dot part"
        ),
        pytest.param(".", ".", "is not a path inside the pack.", id="a lone dot"),
        pytest.param(
            "a\x00b", "a", "holds a character Windows cannot write.", id="a NUL"
        ),
    ],
)
def test_a_name_not_in_normal_form_is_a_bad_path_on_every_system(
    pack: Path,
    tmp_path: Path,
    written: list[str],
    stored: str,
    read_as: str,
    sentence: str,
) -> None:
    """A name is read as the zip stores it. Each of these would read as the name the manifest
    lists: zipfile cuts a NUL and, on Windows, turns a backslash into a slash, and a path
    drops an empty or dot part, so a lone dot is the pack's own folder. Refused as the
    license server words it, before any write."""
    listed(pack, (read_as, b"x"))
    member = (stored_as(stored), b"x")
    archive = zipped(pack, tmp_path / "stored.zip", add=lambda a: added(a, member))

    refusal = refusal_of(archive, tmp_path / "installed")

    assert (refusal.code, refusal.message) == ("BAD_PATH", f"{stored!r} {sentence}")
    assert written == []


def test_a_listed_name_stored_in_normal_form_installs(
    pack: Path, tmp_path: Path
) -> None:
    """The same file stored under the very name the manifest lists installs."""
    listed(pack, ("a/b", b"x"))
    member = (stored_as("a/b"), b"x")
    archive = zipped(pack, tmp_path / "stored.zip", add=lambda a: added(a, member))

    assert install_pack(archive, tmp_path / "installed").id == PACK_ID


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("./jobs/", "'./jobs' is not a path inside the pack."),
        ("jobs//", "'jobs/' is not a path inside the pack."),
        (
            "jobs\\",
            # Only Windows reads it as the folder `jobs/`, stored otherwise.
            "'jobs\\\\' is not in normal form."
            if os.sep == "\\"
            else "'jobs\\\\' is not a path inside the pack.",
        ),
        ("./", "'.' is not a path inside the pack."),
    ],
    ids=["a dot part", "an empty part", "a backslash", "a lone dot"],
)
def test_a_folder_entry_not_in_normal_form_is_a_bad_path(
    pack: Path, tmp_path: Path, written: list[str], name: str, message: str
) -> None:
    """A folder's own entry is held to the same form, but for its closing slash, which the
    sentence leaves out as the license server words it; on Windows `jobs\\` reads as the
    folder `jobs/`."""
    entry = (stored_as(name), b"")
    archive = zipped(pack, tmp_path / "folders.zip", add=lambda a: added(a, entry))

    refusal = refusal_of(archive, tmp_path / "installed")

    assert (refusal.code, refusal.message) == ("BAD_PATH", message)
    assert written == []


@pytest.mark.parametrize(
    "path",
    [
        "jobs/q?.json",
        "a*b",
        'a"b',
        "a<b",
        "a>b",
        "a|b",
        "a\x01b",
        "docs/a\x1f",
        "a\x00b",
    ],
)
def test_a_path_holding_a_character_windows_cannot_hold_is_a_bad_path(
    path: str,
) -> None:
    """The rule a manifest's paths and a zip's names share, whatever system reads them."""
    with pytest.raises(PackRefusedError) as refused_path:
        safe_path(path)

    assert refused_path.value.code == "BAD_PATH"


@pytest.mark.parametrize("path", [".", "./"])
def test_a_path_naming_the_pack_s_own_folder_is_a_bad_path(path: str) -> None:
    """A lone dot names no file in the pack: a manifest lists none there, as no zip holds
    one."""
    with pytest.raises(PackRefusedError) as refused_path:
        safe_path(path)

    assert refused_path.value.code == "BAD_PATH"


@pytest.mark.parametrize(
    ("path", "sentence"),
    [
        ("a:b", "'a:b' is not a path inside the pack."),
        (
            "x?" + "y" * 300,
            f"{'x?' + 'y' * 58!r}... is longer than 255 bytes in UTF-8.",
        ),
        ("\ud800" * 86, repr("\ud800" * 60) + "... is longer than 255 bytes in UTF-8."),
        ("/x", "'/x' is not a path inside the pack."),
        ("a/", "'a/' is not a path inside the pack."),
        ("x?/../y", "'x?/../y' is not a path inside the pack."),
        ("docs/a|b.md", "'docs/a|b.md' holds a character Windows cannot write."),
        ("docs/Nul.md", "'docs/Nul.md' names a file Windows cannot write."),
        ("notes ", "'notes ' names a file Windows cannot write."),
        ("con/a~1", "'con/a~1' names a file Windows cannot write."),
        ("a~1/con", "'a~1/con' could be the Windows short name of another file."),
        (
            "REPORT~1.MD",
            "'REPORT~1.MD' could be the Windows short name of another file.",
        ),
    ],
    ids=[
        "a colon",
        "a long name of a character Windows cannot write",
        "lone surrogates past 255 bytes",
        "a leading slash",
        "a closing slash",
        "a parent part and a character Windows cannot write",
        "a pipe",
        "a device name in a folder",
        "a closing space",
        "a device name above a short name",
        "a short name above a device name",
        "a short name",
    ],
)
def test_a_path_is_refused_in_the_license_server_s_order_and_words(
    path: str, sentence: str
) -> None:
    """The first rule a path breaks names its refusal, checked in the server's order: its
    form, its length in UTF-8, a lone surrogate counted as written, its parts as written,
    its characters, then each part's ending, device name and short name."""
    with pytest.raises(PackRefusedError) as refused_path:
        safe_path(path)

    assert (refused_path.value.code, refused_path.value.message) == (
        "BAD_PATH",
        sentence,
    )


def test_a_path_of_printable_characters_windows_can_hold_is_safe() -> None:
    """The characters the rule leaves out are the only ones it refuses."""
    assert safe_path("jobs/a b (2) [x] #1 'y' é.md").as_posix() == (
        "jobs/a b (2) [x] #1 'y' é.md"
    )


def test_a_symlink_member_is_a_bad_path(pack: Path, tmp_path: Path) -> None:
    """A link could point out of the pack; a pack holds plain files only."""

    def link(archive: zipfile.ZipFile) -> None:
        member = zipfile.ZipInfo("jobs/link")
        member.create_system = 3
        member.external_attr = 0o120777 << 16
        archive.writestr(member, "../../outside")

    archive = zipped(pack, tmp_path / "linked.zip", add=link)

    assert refused(archive, tmp_path / "installed") == "BAD_PATH"


def test_two_names_equal_but_for_case_are_a_bad_path(
    pack: Path, tmp_path: Path
) -> None:
    """On a case-blind disk the second would overwrite the first after it was checked."""
    archive = zipped(
        pack, tmp_path / "cased.zip", add=lambda a: a.writestr("license.md", "x")
    )

    assert refused(archive, tmp_path / "installed") == "BAD_PATH"


def test_an_encrypted_member_is_not_a_pack(pack: Path, tmp_path: Path) -> None:
    """A pack is never encrypted, so one that is was not made by SurfSense's tools."""
    archive = zipped(pack, tmp_path / "locked.zip")
    archive.write_bytes(encrypted(archive.read_bytes(), "LICENSE.md"))

    assert refused(archive, tmp_path / "installed") == "NOT_A_PACK"


def test_bzip2_compression_is_not_a_pack(pack: Path, tmp_path: Path) -> None:
    """Only stored and deflated members are read."""
    archive = zipped(pack, tmp_path / "bzip2.zip", compression=zipfile.ZIP_BZIP2)

    assert refused(archive, tmp_path / "installed") == "NOT_A_PACK"


def test_a_corrupt_deflate_stream_is_not_a_pack(pack: Path, tmp_path: Path) -> None:
    """A member that cannot be inflated refuses the zip rather than failing the install."""
    archive = zipped(pack, tmp_path / "corrupt.zip")
    archive.write_bytes(corrupted(archive.read_bytes(), "LICENSE.md"))

    assert refused(archive, tmp_path / "installed") == "NOT_A_PACK"


def test_a_name_that_is_not_utf8_is_not_a_pack(pack: Path, tmp_path: Path) -> None:
    """A name flagged as UTF-8 that is not cannot be read, so neither can the zip."""
    archive = zipped(
        pack,
        tmp_path / "misnamed.zip",
        compression=zipfile.ZIP_STORED,
        add=lambda a: a.writestr("jobs/é.md", "x"),
    )
    archive.write_bytes(archive.read_bytes().replace("é".encode(), b"\xff\xfe"))

    assert refused(archive, tmp_path / "installed") == "NOT_A_PACK"


def test_a_zip_without_a_manifest_at_its_root_is_not_a_pack(
    pack: Path, tmp_path: Path
) -> None:
    """The pack's files without job-pack.json, at the root or in one folder holding them
    all: some other zip."""
    (pack / MANIFEST).unlink()
    archive = zipped(pack, tmp_path / "no-manifest.zip")

    assert refused(archive, tmp_path / "installed") == "NOT_A_PACK"


def test_members_whose_declared_sizes_pass_the_cap_are_too_large(
    pack: Path, tmp_path: Path, written: list[str]
) -> None:
    """Zipfile stops each member at its declared size, so the sizes bound what an install
    writes: a small zip whose members add up to more than 50 MiB once extracted is too
    large before any file is written."""
    big = zipfile.ZipInfo("big.bin", date_time=(2026, 11, 3, 0, 0, 0))
    big.compress_type = zipfile.ZIP_DEFLATED
    archive = zipped(
        pack,
        tmp_path / "big.zip",
        add=lambda a: a.writestr(big, bytes(MAX_PACK_BYTES + 1)),
    )

    assert archive.stat().st_size < MAX_PACK_BYTES
    assert refused(archive, tmp_path / "installed") == "PACK_TOO_LARGE"
    assert written == []


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(lambda data: b"[]\n", id="not an object"),
        pytest.param(lambda data: b"\xef\xbb\xbf" + data, id="a byte-order mark"),
        pytest.param(lambda data: data + b"\xff", id="not UTF-8"),
        pytest.param(lambda data: b"{", id="not JSON"),
        pytest.param(
            lambda data: b"[" * 100_000 + b"]" * 100_000, id="nested 100,000 deep"
        ),
    ],
)
def test_a_manifest_that_is_not_one_json_object_is_a_bad_manifest(
    pack: Path, tmp_path: Path, change: Callable[[bytes], bytes]
) -> None:
    """The license server's cases: job-pack.json is UTF-8 JSON with no byte-order mark, one
    object, read without running out of stack."""
    path = pack / MANIFEST
    path.write_bytes(change(path.read_bytes()))
    archive = zipped(pack, tmp_path / "manifest.zip")

    assert refused(archive, tmp_path / "installed") == "BAD_MANIFEST"


def _set(field: str, value):
    return lambda manifest: manifest.update({field: value})


def _set_job(field: str, value):
    return lambda manifest: manifest["jobs"][0].update({field: value})


def _second_job_with_the_same_key(manifest: dict) -> None:
    manifest["jobs"].append(dict(manifest["jobs"][0]))


def _misnamed_skill(manifest: dict) -> None:
    manifest["files"]["skills/questions/SKILL.md"] = "0" * 64
    manifest["jobs"][0]["skill"] = "skills/questions"


@pytest.mark.parametrize(
    "edit",
    [
        pytest.param(_set("schema", "surfsense-job-pack/2"), id="another schema"),
        pytest.param(_set("id", "Sample-Jobs"), id="an id in capitals"),
        pytest.param(_set("version", "1.0"), id="a two-part version"),
        # The app sends it back as installed_version, each part at most 9 digits.
        pytest.param(_set("version", "1.0.2026110301"), id="a ten-digit part"),
        # Python's \d takes any script's digits, which no header can carry.
        pytest.param(_set("version", "1.0.\u0661"), id="a digit that is not ASCII"),
        pytest.param(_set("name", " "), id="a blank name"),
        pytest.param(_set("publisher", 7), id="a publisher that is not text"),
        pytest.param(lambda m: m.pop("description"), id="no description"),
        pytest.param(_set("access", "trial"), id="an unknown access"),
        pytest.param(_set("license_file", "TERMS.txt"), id="an unlisted license"),
        pytest.param(_set("files", {}), id="no files"),
        pytest.param(
            lambda m: m["files"].update({"LICENSE.txt": "abc"}), id="a short sha256"
        ),
        pytest.param(_set("jobs", []), id="no jobs"),
        pytest.param(_set("jobs", ["job"]), id="a job that is not an object"),
        pytest.param(_set_job("key", "Questions"), id="a job key in capitals"),
        pytest.param(_second_job_with_the_same_key, id="a job key used twice"),
        pytest.param(_set_job("name", " "), id="a blank job name"),
        pytest.param(
            lambda m: m["jobs"][0].pop("description"), id="a job without a description"
        ),
        pytest.param(_set_job("runner", "workbook-rows"), id="a runner without one"),
        pytest.param(_set_job("config", "jobs/none.json"), id="an unlisted config"),
        pytest.param(_set_job("skill", "skills/x"), id="a skill without SKILL.md"),
        pytest.param(_misnamed_skill, id="a skill folder misnamed"),
        pytest.param(_set_job("entitlement", "job_q"), id="an entitlement in lower"),
    ],
)
def test_each_manifest_rule_refuses_a_bad_manifest(
    pack: Path, tmp_path: Path, edit: Callable[[dict], object]
) -> None:
    """The license server's cases, the same list: each signed again, so the manifest's
    rules alone refuse it."""
    path = pack / MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    edit(manifest)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    sign_pack(pack)
    archive = zipped(pack, tmp_path / "manifest.zip")

    assert refused(archive, tmp_path / "installed") == "BAD_MANIFEST"
