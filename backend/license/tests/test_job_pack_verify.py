"""A zip is served only once it passes contract 6's zip section, the first failing check named."""

from __future__ import annotations

import base64
import hashlib
import re
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from license.job_packs import signature
from license.job_packs.manifest import PackRefusedError
from license.job_packs.verify import MAX_PACK_BYTES, verified_pack
from license.tests.job_pack_samples import (
    QUESTIONNAIRE,
    TEST_PACK_KEY,
    TEST_PACK_PUBLIC_KEY_HEX,
    Member,
    corrupt_member,
    encrypted,
    pack_zip,
    public_hex,
    symlink,
    with_name_bytes,
)

pytestmark = pytest.mark.unit

SAMPLE_PUBLIC_KEY = (
    Path(__file__).resolve().parents[3]
    / "docs/contracts/job-pack-sample/public-key.hex"
)
OTHER_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32, 64)))
NAME = "sample-jobs-1.0.0.zip"


def refusal(data: bytes, name: str = NAME) -> str:
    with pytest.raises(PackRefusedError) as refused:
        verified_pack(data, name=name)
    assert refused.value.message
    return refused.value.code


def edited(path: str, change):
    """A member_edit changing only `path`'s bytes."""
    return lambda name, data: change(data) if name == path else data


def folder_entry(name: str) -> zipfile.ZipInfo:
    return zipfile.ZipInfo(name, date_time=(2026, 11, 3, 0, 0, 0))


# accepted ---------------------------------------------------------------------


def test_a_sealed_signed_pack_is_accepted(trusted_pack_key) -> None:
    pack = verified_pack(pack_zip(), name=NAME)

    assert (pack.id, pack.version, pack.filename) == ("sample-jobs", "1.0.0", NAME)
    assert [(job.key, job.runner, job.entitlement) for job in pack.jobs] == [
        QUESTIONNAIRE
    ]
    assert pack.data == pack_zip()
    assert pack.data.hex() not in repr(pack)


def test_the_signed_bytes_are_the_apps() -> None:
    assert (
        signature.signed_payload({"b": 1, "a": "é"})
        == b'surfsense-job-pack/1\n{"a":"\xc3\xa9","b":1}'
    )


def test_a_runner_the_server_never_heard_of_is_accepted(trusted_pack_key) -> None:
    """Which runners an app has is the selection's business, not the check's."""
    data = pack_zip(jobs=(("sample-cells", "spreadsheet-cells/7", "JOB_CELLS"),))

    assert verified_pack(data, name=NAME).runners == {"spreadsheet-cells/7"}


def test_a_pack_signed_by_two_trusted_keys_is_accepted(monkeypatch) -> None:
    """A rotation signs with the old key and the new one."""
    monkeypatch.setattr(
        signature,
        "PACK_PUBLIC_KEYS_HEX",
        (public_hex(OTHER_KEY), TEST_PACK_PUBLIC_KEY_HEX),
    )

    pack = verified_pack(pack_zip(keys=(OTHER_KEY, TEST_PACK_KEY)), name=NAME)

    assert pack.id == "sample-jobs"


def test_a_directory_entry_carries_nothing_and_is_accepted(trusted_pack_key) -> None:
    assert verified_pack(
        pack_zip(extra_members=((folder_entry("jobs/"), b""),)), name=NAME
    )


# refused ----------------------------------------------------------------------


def test_the_first_check_that_fails_names_the_refusal(trusted_pack_key) -> None:
    """Unsigned, free and holding an unlisted file: the signature is checked first."""
    data = pack_zip(keys=(), access="free", extra_members=(("notes.txt", b"x"),))

    assert refusal(data) == "PACK_NOT_SIGNED"


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"not a zip", id="not a zip"),
        pytest.param(pack_zip(wrap_folder="sample-jobs"), id="a wrapping folder"),
        pytest.param(encrypted(pack_zip(), "LICENSE.txt"), id="an encrypted member"),
        pytest.param(
            pack_zip(compression=zipfile.ZIP_LZMA), id="compressed other than deflate"
        ),
        pytest.param(
            corrupt_member(pack_zip(compression=zipfile.ZIP_DEFLATED), "LICENSE.txt"),
            id="a corrupt deflate stream",
        ),
        pytest.param(
            with_name_bytes(
                pack_zip(extra_members=(("café.txt", b"x"),)),
                "café.txt",
                b"caf\xff\xfe.txt",
            ),
            id="a name that is not UTF-8",
        ),
    ],
)
def test_a_zip_that_cannot_be_read_as_a_pack_is_not_a_pack(
    trusted_pack_key, data: bytes
) -> None:
    assert refusal(data) == "NOT_A_PACK"


def test_a_pack_over_the_cap_is_too_large(trusted_pack_key) -> None:
    assert refusal(b"PK" + bytes(MAX_PACK_BYTES)) == "PACK_TOO_LARGE"


def test_members_whose_declared_sizes_pass_the_cap_are_too_large(
    trusted_pack_key,
) -> None:
    """Zipfile stops each member at its declared size, so the sizes bound the memory."""
    big = zipfile.ZipInfo("big.bin", date_time=(2026, 11, 3, 0, 0, 0))
    big.compress_type = zipfile.ZIP_DEFLATED

    data = pack_zip(extra_members=((big, bytes(MAX_PACK_BYTES + 1)),))

    assert len(data) < MAX_PACK_BYTES
    assert refusal(data) == "PACK_TOO_LARGE"


def test_more_than_a_thousand_members_is_too_large(trusted_pack_key) -> None:
    extra = tuple((f"extra/{n}.txt", b"") for n in range(1000))

    assert refusal(pack_zip(extra_members=extra)) == "PACK_TOO_LARGE"


def test_folder_entries_count_toward_the_thousand_members(trusted_pack_key) -> None:
    """Contract 6 bounds the members, folders among them, before each is looked at."""
    folders = tuple((folder_entry(f"jobs/{n}/"), b"") for n in range(997))

    assert refusal(pack_zip(extra_members=folders)) == "PACK_TOO_LARGE"


def test_a_folder_entry_carrying_data_is_not_a_pack(trusted_pack_key) -> None:
    """A folder carries nothing, so bytes in one would be served unlisted and unsigned."""
    data = pack_zip(extra_members=((folder_entry("jobs/"), b"x" * 1024),))

    assert refusal(data) == "NOT_A_PACK"


@pytest.mark.parametrize(
    "member",
    [
        ("../x", b"x"),
        ("/x", b"x"),
        ("a\\b", b"x"),
        ("c:x", b"x"),
        ("a//b", b"x"),
        ("a/./b", b"x"),
        ("a\x00b", b"x"),
        symlink("jobs/link", "LICENSE.txt"),
        ("license.txt", b"x"),
        ("nul", b"x"),
        ("com1.txt", b"x"),
        ("docs/AUX.md", b"x"),
        ("dir./x", b"x"),
        ("x ", b"x"),
    ],
    ids=[
        "a parent part",
        "an absolute name",
        "a backslash",
        "a drive",
        "an empty part",
        "a dot part",
        "a NUL",
        "a symlink",
        "a name equal but for case",
        "a device name",
        "a device name with an extension",
        "a device name in a folder",
        "a part ending in a dot",
        "a part ending in a space",
    ],
)
def test_a_member_name_the_app_could_not_write_safely_is_a_bad_path(
    trusted_pack_key, member
) -> None:
    assert refusal(pack_zip(extra_members=(member,))) == "BAD_PATH"


def listed(*members: Member) -> dict:
    """pack_zip's arguments for members the manifest lists, so only their names are at fault."""

    def listing(manifest: dict) -> None:
        for name, data in members:
            if isinstance(name, str):
                manifest["files"][name] = hashlib.sha256(data).hexdigest()

    return {"manifest_edit": listing, "extra_members": members}


def test_listed_files_in_folders_spelled_one_way_are_accepted(
    trusted_pack_key,
) -> None:
    data = pack_zip(**listed(("docs/a.txt", b"a"), ("docs/b.txt", b"b")))

    assert verified_pack(data, name=NAME)


def test_names_at_the_rules_edges_are_accepted(trusted_pack_key) -> None:
    """255 bytes in UTF-8, and a tilde that no Windows short name could end in."""
    data = pack_zip(
        **listed(
            ("docs/" + "x" * 250, b"a"),
            ("é" * 127 + "x", b"b"),
            ("notes~v2.md", b"c"),
            ("archive~1.tar.gz", b"d"),
        )
    )

    assert verified_pack(data, name=NAME)


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
    trusted_pack_key, members
) -> None:
    """Contract 6 refuses these on every system, the app's too: on Windows they fail
    or land under another name, and a short name opens the file it is short for."""
    assert refusal(pack_zip(**listed(*members))) == "BAD_PATH"


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
def test_a_name_past_255_bytes_is_a_bad_path(trusted_pack_key, name: str) -> None:
    """No disk holds a name part past 255 bytes, and a longer name costs its checks more."""
    assert refusal(pack_zip(**listed((name, b"x")))) == "BAD_PATH"


def test_a_listed_path_past_255_bytes_is_a_bad_path_though_no_member_has_it(
    trusted_pack_key,
) -> None:
    def long_path(manifest: dict) -> None:
        manifest["files"]["docs/" + "x" * 251] = hashlib.sha256(b"x").hexdigest()

    assert refusal(pack_zip(manifest_edit=long_path)) == "BAD_PATH"


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
def test_each_manifest_rule_refuses_a_bad_manifest(trusted_pack_key, edit) -> None:
    assert refusal(pack_zip(manifest_edit=edit)) == "BAD_MANIFEST"


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
    trusted_pack_key, change
) -> None:
    data = pack_zip(member_edit=edited("job-pack.json", change))

    assert refusal(data) == "BAD_MANIFEST"


def test_an_unsigned_pack_is_not_signed(trusted_pack_key) -> None:
    assert refusal(pack_zip(keys=())) == "PACK_NOT_SIGNED"


@pytest.mark.parametrize(
    "kw",
    [
        pytest.param({"keys": (OTHER_KEY,)}, id="another key"),
        pytest.param(
            {"keys": (TEST_PACK_KEY, OTHER_KEY)}, id="a second line by an untrusted key"
        ),
        pytest.param({"keys": (TEST_PACK_KEY,) * 9}, id="nine lines"),
        pytest.param({"sig_lines": ()}, id="no line"),
        pytest.param({"sig_lines": (base64.b64encode(bytes(63)),)}, id="63 bytes"),
        pytest.param({"sig_lines": (b"not base64!",)}, id="not base64"),
        pytest.param(
            {
                "member_edit": edited(
                    "job-pack.json", lambda d: d.replace(b"Sample jobs", b"Other jobs")
                )
            },
            id="the manifest changed after signing",
        ),
        pytest.param(
            {
                "manifest_edit": _set("description", "\ud800"),
                "sig_lines": (base64.b64encode(bytes(64)),),
            },
            id="a manifest no key could sign",
        ),
    ],
)
def test_a_signature_that_does_not_verify_on_every_line_is_bad(
    trusted_pack_key, kw
) -> None:
    assert refusal(pack_zip(**kw)) == "PACK_BAD_SIGNATURE"


def test_eight_lines_each_by_a_trusted_key_are_accepted(trusted_pack_key) -> None:
    assert verified_pack(pack_zip(keys=(TEST_PACK_KEY,) * 8), name=NAME)


def test_a_file_the_manifest_does_not_list_is_unlisted(trusted_pack_key) -> None:
    data = pack_zip(extra_members=(("notes.txt", b"x"),))

    assert refusal(data) == "PACK_FILE_UNLISTED"


def test_a_listed_file_not_in_the_zip_is_missing(trusted_pack_key) -> None:
    def listed_but_absent(manifest: dict) -> None:
        manifest["files"]["jobs/extra.json"] = hashlib.sha256(b"{}").hexdigest()

    assert refusal(pack_zip(manifest_edit=listed_but_absent)) == "PACK_FILE_MISSING"


def test_a_file_changed_after_sealing_is_changed(trusted_pack_key) -> None:
    data = pack_zip(member_edit=edited("LICENSE.txt", lambda _: b"Other terms.\n"))

    assert refusal(data) == "PACK_FILE_CHANGED"


def test_a_free_pack_is_not_served(trusted_pack_key) -> None:
    assert refusal(pack_zip(access="free")) == "PACK_NOT_PAID"


def test_a_paid_job_without_an_entitlement_is_refused(trusted_pack_key) -> None:
    """A license would get it without having bought it."""
    data = pack_zip(jobs=(QUESTIONNAIRE, ("sample-extra", "workbook-rows/1", None)))

    assert refusal(data) == "PACK_JOB_WITHOUT_ENTITLEMENT"


def test_a_zip_named_for_another_version_is_a_mismatch(trusted_pack_key) -> None:
    assert refusal(pack_zip(), name="sample-jobs-1.0.1.zip") == "PACK_NAME_MISMATCH"


# keys -------------------------------------------------------------------------


def test_no_test_key_is_trusted_in_production() -> None:
    assert (
        signature.PACK_PUBLIC_KEYS_HEX
        == (
            "1545536e7caeffd794d26d01cfc22e5ef01d07ddf10894dfe517c2d6afdb9230",  # pragma: allowlist secret
        )
    )
    assert all(re.fullmatch(r"[0-9a-f]{64}", k) for k in signature.PACK_PUBLIC_KEYS_HEX)
    assert SAMPLE_PUBLIC_KEY.read_text().strip() not in signature.PACK_PUBLIC_KEYS_HEX
    assert TEST_PACK_PUBLIC_KEY_HEX not in signature.PACK_PUBLIC_KEYS_HEX
