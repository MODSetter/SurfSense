"""CI signs the list; the app trusts only bytes that verify with the key it compiles in."""

import base64
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from registry_check.signing.sign import sign_registry
from registry_check.signing.verify import verify_registry
from tests.registry_files import SQUARE_SVG, valid_entry, write_registry

PRODUCTION_PUBLIC_KEY = (
    "9498a1606105a625feeaa655648df03885410421a387478a72ec763188f10395"
)
COMMITTED = Path(__file__).resolve().parents[2] / "published" / "plugins.json"


def new_key() -> tuple[str, str]:
    """A fresh key pair: base64 raw private key, hex raw public key."""
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(private).decode(), public.hex()


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path, _ = write_registry(
        tmp_path,
        [valid_entry(icon="acme.svg"), valid_entry(id="plain")],
        icons={"acme.svg": SQUARE_SVG},
    )
    return path


@pytest.fixture
def registry(source: Path) -> Path:
    """Where signing writes the copy the server publishes."""
    return source.parent / "published" / "plugins.json"


def sign(source: Path, private: str, now: datetime | None = None) -> None:
    sign_registry(source, source.parent / "published", private, now=now)


def test_a_signed_list_verifies(source, registry):
    private, public = new_key()
    sign(source, private)
    assert verify_registry(registry, public)


def test_one_changed_byte_fails(source, registry):
    private, public = new_key()
    sign(source, private)
    content = registry.read_bytes()
    registry.write_bytes(content.replace(b'"Acme"', b'"Acmf"', 1))
    assert not verify_registry(registry, public)


def test_another_key_fails(source, registry):
    private, _ = new_key()
    _, other_public = new_key()
    sign(source, private)
    assert not verify_registry(registry, other_public)


def test_a_missing_signature_fails(source):
    _, public = new_key()
    registry = source
    assert not verify_registry(registry, public)


def test_signing_adds_the_date_and_each_icons_hash(source, registry):
    private, _ = new_key()
    sign(source, private, now=datetime(2026, 10, 12, 9, 30, tzinfo=UTC))
    signed = json.loads(registry.read_text())
    assert signed["generated_at"] == "2026-10-12T09:30:00Z"
    acme, plain = signed["plugins"]
    assert acme["icon_sha256"] == hashlib.sha256(SQUARE_SVG).hexdigest()
    assert "icon_sha256" not in plain


def test_the_signed_file_has_stable_formatting(source, registry):
    private, _ = new_key()
    sign(source, private, now=datetime(2026, 10, 12, tzinfo=UTC))
    text = registry.read_text()
    assert text.endswith("}\n")
    assert text.startswith('{\n  "schema_version": 1,\n  "generated_at": ')
    first = registry.read_bytes()
    sign(source, private, now=datetime(2026, 10, 12, tzinfo=UTC))
    assert registry.read_bytes() == first


def test_the_date_is_utc_with_a_z(source, registry):
    private, _ = new_key()
    sign(source, private)
    generated_at = json.loads(registry.read_text())["generated_at"]
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", generated_at)


def test_the_source_list_is_never_rewritten(source):
    before = source.read_bytes()
    private, _ = new_key()
    sign(source, private)
    assert source.read_bytes() == before


def test_a_key_that_is_not_32_raw_bytes_is_refused(source):
    with pytest.raises(ValueError, match="32"):
        sign(source, base64.b64encode(b"short").decode())


# A pull request edits the list after it was signed, so only the signing job asks.
@pytest.mark.skipif(
    os.environ.get("REGISTRY_VERIFY_COMMITTED") != "1",
    reason="set REGISTRY_VERIFY_COMMITTED=1 where the committed list was just signed",
)
def test_the_committed_list_verifies_with_the_production_key():
    assert verify_registry(COMMITTED, PRODUCTION_PUBLIC_KEY)
