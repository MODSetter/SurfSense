"""Icons are drawn by strangers and shown in the app: small, square, inert."""

import struct
import zlib
from pathlib import Path

import pytest

from registry_check.static.checked_list import problems_in
from tests.registry_files import SQUARE_SVG, valid_entry, write_registry


def png(width: int, height: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"".join(b"\0" + b"\0\0\0" * width for _ in range(height)))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", pixels)
        + chunk(b"IEND", b"")
    )


def problems(tmp_path: Path, icon_name: str | None, icons: dict[str, bytes]):
    entry = valid_entry(icon=icon_name) if icon_name else valid_entry()
    registry, first_party = write_registry(tmp_path, [entry], icons=icons)
    return problems_in(registry, first_party)


def test_a_square_svg_and_a_square_png_pass(tmp_path):
    assert problems(tmp_path, "acme.svg", {"acme.svg": SQUARE_SVG}) == []
    assert problems(tmp_path / "png", "acme.png", {"acme.png": png(64, 64)}) == []


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("missing.svg", None),
        ("acme.gif", b"GIF89a"),
        ("acme.svg", SQUARE_SVG + b"<!--" + b"x" * 33 * 1024 + b"-->"),
        ("acme.svg", SQUARE_SVG.replace(b"<rect", b"<script>alert(1)</script><rect")),
        ("acme.svg", SQUARE_SVG.replace(b"<rect", b'<rect onclick="alert(1)"')),
        (
            "acme.svg",
            SQUARE_SVG.replace(
                b"<rect", b'<image href="https://evil.example/x.png"/><rect'
            ),
        ),
        (
            "acme.svg",
            SQUARE_SVG.replace(b"<rect", b'<use href="//evil.example/x"/><rect'),
        ),
        (
            "acme.svg",
            SQUARE_SVG.replace(
                b"<rect", b'<style>@import "https://e.example/a.css";</style><rect'
            ),
        ),
        (
            "acme.svg",
            SQUARE_SVG.replace(b'fill="#2563eb"', b'style="fill:url(//e.example/p)"'),
        ),
        ("acme.svg", SQUARE_SVG.replace(b"0 0 64 64", b"0 0 64 32")),
        ("acme.svg", SQUARE_SVG.replace(b' viewBox="0 0 64 64"', b"")),
        ("acme.svg", b"<svg"),
        ("acme.svg", b'<!DOCTYPE svg [<!ENTITY a "a">]>' + SQUARE_SVG),
        ("acme.png", png(64, 32)),
        ("acme.png", png(32, 32)),
        ("acme.png", SQUARE_SVG),
    ],
)
def test_a_bad_icon_is_named(tmp_path, name, content):
    icons = {} if content is None else {name: content}
    found = problems(tmp_path, name, icons)
    assert len(found) == 1, found
    assert found[0].startswith('plugins[0] "acme": icon: '), found


def test_an_icon_cannot_point_outside_the_icons_folder(tmp_path):
    found = problems(tmp_path, "../plugins.json", {})
    assert len(found) == 1
    assert "icon:" in found[0]


def test_every_icon_file_belongs_to_an_entry(tmp_path):
    found = problems(tmp_path, None, {"stray.svg": SQUARE_SVG})
    assert found == ["icons/stray.svg: no entry uses it"]
