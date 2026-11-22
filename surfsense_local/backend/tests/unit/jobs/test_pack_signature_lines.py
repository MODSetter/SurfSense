"""A pack's signature holds one to eight lines, one per key that signed it; the app installs the
pack when any line is made by a key it trusts, so a key rotation can sign with the old and the
new."""

import base64
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from modules.jobs.packs.install import install_pack
from modules.jobs.packs.installed import installed_packs
from modules.jobs.packs.manifest import SIGNATURE, PackRefusedError
from tests.job_pack_samples import PACK_ID, TEST_PACK_KEY, write_questionnaire_pack

pytestmark = pytest.mark.unit

# A key no release trusts, made from a fixed seed so its lines are the same every run.
STRANGER = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))


def trusted_line(tmp_path: Path) -> bytes:
    """The test key's signature of the questionnaire pack, as one line."""
    pack = write_questionnaire_pack(tmp_path / "signed")
    return (pack / SIGNATURE).read_bytes().strip()


def test_one_line_installs_as_every_pack_signed_so_far(tmp_path: Path) -> None:
    """A signature of one line and a newline, as SurfSense's script writes it."""
    pack = write_questionnaire_pack(tmp_path / "pack")

    assert (pack / SIGNATURE).read_bytes().count(b"\n") == 1
    assert install_pack(pack, tmp_path / "installed").id == PACK_ID


@pytest.mark.parametrize(
    "keys", [(STRANGER, TEST_PACK_KEY), (TEST_PACK_KEY, STRANGER)], ids=["new", "old"]
)
def test_two_lines_with_one_trusted_install(
    tmp_path: Path, keys: tuple[Ed25519PrivateKey, ...]
) -> None:
    """A pack signed with the old key and the new installs on an app that trusts either."""
    pack = write_questionnaire_pack(tmp_path / "pack", signed_by=keys)
    root = tmp_path / "installed"

    install_pack(pack, root)

    assert [p.manifest.id for p in installed_packs(root)] == [PACK_ID]


def test_eight_lines_and_blank_ones_install_when_one_is_trusted(tmp_path: Path) -> None:
    """Blank lines count for nothing, and eight signatures are the most a pack carries."""
    line = trusted_line(tmp_path)
    stranger = base64.b64encode(STRANGER.sign(b"another pack"))
    pack = write_questionnaire_pack(
        tmp_path / "pack", sig_lines=[b"", *[stranger] * 7, b"", line, b""]
    )

    assert install_pack(pack, tmp_path / "installed").id == PACK_ID


def test_lines_ended_with_crlf_install(tmp_path: Path) -> None:
    """A line ending is no part of a line, so a signature written with CRLF installs."""
    pack = write_questionnaire_pack(
        tmp_path / "pack", sig_lines=[trusted_line(tmp_path) + b"\r", b"\r"]
    )

    assert install_pack(pack, tmp_path / "installed").id == PACK_ID


def test_a_signature_no_trusted_key_made_is_refused(tmp_path: Path) -> None:
    """Two lines, neither by a key the app trusts."""
    other = Ed25519PrivateKey.from_private_bytes(bytes(range(2, 34)))
    pack = write_questionnaire_pack(tmp_path / "pack", signed_by=(STRANGER, other))

    with pytest.raises(PackRefusedError) as refused:
        install_pack(pack, tmp_path / "installed")

    assert refused.value.code == "PACK_BAD_SIGNATURE"
    assert "does not match" in refused.value.message


@pytest.mark.parametrize(
    "lines",
    [
        pytest.param(lambda line: [line] * 9, id="nine lines"),
        pytest.param(lambda _line: [base64.b64encode(bytes(63))], id="63 bytes"),
        pytest.param(lambda line: [line + b"*"], id="not base64"),
        # Each line is the standard base64 alone, as the license server reads it.
        pytest.param(lambda line: [line + b" "], id="a space after it"),
        pytest.param(lambda line: [b" " + line], id="a space before it"),
        pytest.param(lambda line: [b"\t" + line], id="a tab before it"),
        pytest.param(lambda line: [line + b"\t"], id="a tab after it"),
    ],
)
def test_a_signature_that_cannot_be_read_is_refused(tmp_path: Path, lines) -> None:
    """Nine lines are more than any rotation needs, and a line that is no Ed25519 signature
    is no signature, even beside a trusted one: nor is one with a space or a tab around its
    base64, which the license server never serves."""
    pack = write_questionnaire_pack(
        tmp_path / "pack", sig_lines=lines(trusted_line(tmp_path))
    )

    with pytest.raises(PackRefusedError) as refused:
        install_pack(pack, tmp_path / "installed")

    assert refused.value.code == "PACK_BAD_SIGNATURE"
    assert refused.value.message == "The pack's signature cannot be read."
