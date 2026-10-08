"""An Office file opened read-only as its parts, changed in memory and saved as a copy.

Every part is parsed with entities, DTDs and the network off, and decompressed
sizes are counted as they stream, so a hostile file can neither reach out nor
exhaust memory.
"""

import lzma
import posixpath
import zipfile
import zlib
from pathlib import Path
from typing import BinaryIO
from urllib.parse import unquote

from lxml import etree

# Far above any real document; a zip bomb passes them only by lying in headers,
# and reads are counted as they stream.
PART_LIMIT = 64 * 1024 * 1024
TOTAL_LIMIT = 512 * 1024 * 1024
ENTRY_LIMIT = 10_000

_OLE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
_CONTENT_TYPES = "[Content_Types].xml"
_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_PR = "http://schemas.openxmlformats.org/package/2006/relationships"
_RELS_TYPE = "application/vnd.openxmlformats-package.relationships+xml"
_CHUNK = 1024 * 1024
# What a corrupt or truncated entry raises while it streams.
_DAMAGED = (
    zipfile.BadZipFile,
    zlib.error,
    lzma.LZMAError,
    EOFError,
    NotImplementedError,
    OSError,
)


class PackageRefusedError(Exception):
    """The file cannot be opened safely as an Office package."""

    def __init__(self, code: str, values: dict[str, str | int], message: str) -> None:
        super().__init__(message)
        self.code = code
        self.values = values
        self.message = message


def _parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False, load_dtd=False, no_network=True, huge_tree=False
    )


def parse_xml(data: bytes, part: str) -> etree._Element:
    """Parse one part safely; a DOCTYPE or broken XML refuses the file."""
    try:
        root = etree.fromstring(data, _parser())
    except etree.XMLSyntaxError as error:
        raise PackageRefusedError(
            "UNSAFE_XML", {"part": part}, f"{part} is not well-formed XML."
        ) from error
    if root.getroottree().docinfo.doctype:
        raise PackageRefusedError(
            "UNSAFE_XML",
            {"part": part, "reason": "doctype"},
            f"{part} declares a DOCTYPE, which Office never writes.",
        )
    return root


def rels_name(part: str) -> str:
    """The relationships part of a part; the package's own for ``""``."""
    folder, file = posixpath.split(part)
    return posixpath.join(folder, "_rels", f"{file}.rels")


def _resolve(source: str, target: str) -> str:
    target = unquote(target.split("#", 1)[0])
    if target.startswith("/"):
        return posixpath.normpath(target.lstrip("/"))
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target))


def _relative(source: str, target: str) -> str:
    return posixpath.relpath(target, posixpath.dirname(source) or ".")


class Package:
    """The parts of one Office file, in zip order; nothing touches the file on disk."""

    def __init__(self, path: Path, archive: zipfile.ZipFile) -> None:
        self._path = path
        self._infos = {info.filename: info for info in archive.infolist()}
        self.names: list[str] = [info.filename for info in archive.infolist()]
        self._data: dict[str, bytes] = {}
        self._read_total = 0

    def read(self, name: str) -> bytes:
        if name in self._data:
            return self._data[name]
        with zipfile.ZipFile(self._path) as archive:
            return self._read_from(archive, name)

    def _read_from(self, archive: zipfile.ZipFile, name: str) -> bytes:
        if name in self._data:
            return self._data[name]
        if name not in self._infos:
            raise KeyError(name)
        try:
            with archive.open(self._infos[name]) as stream:
                data = self._capped(name, stream)
        except _DAMAGED as error:
            raise PackageRefusedError(
                "NOT_A_PACKAGE",
                {"part": name},
                f"{name} is damaged inside the file; ask for a copy that opens in Office.",
            ) from error
        self._data[name] = data
        return data

    def _capped(self, name: str, stream: BinaryIO) -> bytes:
        chunks: list[bytes] = []
        size = 0
        while chunk := stream.read(_CHUNK):
            size += len(chunk)
            self._read_total += len(chunk)
            if size > PART_LIMIT:
                raise _too_large(name, PART_LIMIT)
            if self._read_total > TOTAL_LIMIT:
                raise _too_large(name, TOTAL_LIMIT)
            chunks.append(chunk)
        return b"".join(chunks)

    def xml(self, name: str) -> etree._Element:
        return parse_xml(self.read(name), name)

    def set_xml(self, name: str, root: etree._Element) -> None:
        declared = True
        standalone = True
        if name in self.names:
            head = self.read(name).lstrip(b"\xef\xbb\xbf")[:200]
            declared = head.startswith(b"<?xml")
            standalone = b'standalone="yes"' in head or b"standalone='yes'" in head
        body = etree.tostring(root, encoding="UTF-8")
        if declared:
            head = '<?xml version="1.0" encoding="UTF-8"'
            head += ' standalone="yes"?>\r\n' if standalone else "?>\r\n"
            body = head.encode() + body
        self.set_bytes(name, body)

    def set_bytes(self, name: str, data: bytes) -> None:
        if name not in self.names:
            self.names.append(name)
        self._data[name] = data

    def content_type(self, name: str) -> str | None:
        return _type_in(self.xml(_CONTENT_TYPES), name)

    def relationships(self, source: str) -> list[etree._Element]:
        """The Relationship elements of a part (``""`` for the package); none if absent."""
        name = rels_name(source)
        if name not in self.names:
            return []
        return list(self.xml(name).iter(f"{{{_PR}}}Relationship"))

    def related(self, source: str, rel_type: str) -> list[str]:
        """Part names an internal relationship of this type points at, in order."""
        return [
            _resolve(source, rel.get("Target", ""))
            for rel in self.relationships(source)
            if rel.get("Type") == rel_type and rel.get("TargetMode") != "External"
        ]

    def remove(self, name: str) -> None:
        for entry in (name, rels_name(name)):
            if entry in self.names:
                self.names.remove(entry)
                self._data.pop(entry, None)
        for rels in [n for n in self.names if n.endswith(".rels")]:
            source = _rels_source(rels)
            root = self.xml(rels)
            dangling = [
                rel
                for rel in root.iter(f"{{{_PR}}}Relationship")
                if rel.get("TargetMode") != "External"
                and _resolve(source, rel.get("Target", "")) == name
            ]
            if dangling:
                for rel in dangling:
                    root.remove(rel)
                self.set_xml(rels, root)
        types = self.xml(_CONTENT_TYPES)
        overrides = [
            o
            for o in types.iter(f"{{{_CT}}}Override")
            if o.get("PartName", "").lstrip("/").lower() == name.lower()
        ]
        if overrides:
            for override in overrides:
                types.remove(override)
            self.set_xml(_CONTENT_TYPES, types)

    def add_part(
        self,
        name: str,
        root: etree._Element,
        content_type: str,
        rel_from: str,
        rel_type: str,
    ) -> str:
        """Add a part with its content type and a relationship to it; returns that rId."""
        self.set_xml(name, root)
        types = self.xml(_CONTENT_TYPES)
        override = etree.SubElement(types, f"{{{_CT}}}Override")
        override.set("PartName", f"/{name}")
        override.set("ContentType", content_type)
        self.set_xml(_CONTENT_TYPES, types)

        rels = rels_name(rel_from)
        if rels in self.names:
            rels_root = self.xml(rels)
        else:
            rels_root = etree.Element(f"{{{_PR}}}Relationships", nsmap={None: _PR})
            if self.content_type(rels) != _RELS_TYPE:
                default = etree.SubElement(types, f"{{{_CT}}}Default")
                default.set("Extension", "rels")
                default.set("ContentType", _RELS_TYPE)
                types.insert(0, default)
                self.set_xml(_CONTENT_TYPES, types)
        taken = {rel.get("Id") for rel in rels_root}
        number = len(taken) + 1
        while f"rId{number}" in taken:
            number += 1
        rid = f"rId{number}"
        rel = etree.SubElement(rels_root, f"{{{_PR}}}Relationship")
        rel.set("Id", rid)
        rel.set("Type", rel_type)
        rel.set("Target", _relative(rel_from, name) if rel_from else name)
        self.set_xml(rels, rels_root)
        return rid

    def save(self, out: Path) -> None:
        with (
            zipfile.ZipFile(self._path) as source,
            zipfile.ZipFile(out, "w") as archive,
        ):
            for name in self.names:
                info = self._infos.get(name)
                data = self._read_from(source, name)
                if info is None:
                    archive.writestr(name, data, zipfile.ZIP_DEFLATED)
                else:
                    archive.writestr(_like(info), data)


def _like(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    copy = zipfile.ZipInfo(info.filename, date_time=info.date_time)
    copy.compress_type = info.compress_type
    copy.external_attr = info.external_attr
    return copy


def _type_in(types: etree._Element, name: str) -> str | None:
    for override in types.iter(f"{{{_CT}}}Override"):
        if override.get("PartName", "").lstrip("/").lower() == name.lower():
            return override.get("ContentType")
    base = posixpath.basename(name)
    extension = base.rpartition(".")[2].lower() if "." in base else ""
    for default in types.iter(f"{{{_CT}}}Default"):
        if default.get("Extension", "").lower() == extension:
            return default.get("ContentType")
    return None


def _rels_source(rels: str) -> str:
    folder, file = posixpath.split(rels)
    return posixpath.join(posixpath.dirname(folder), file.removesuffix(".rels"))


def _too_large(part: str, limit: int) -> PackageRefusedError:
    return PackageRefusedError(
        "PART_TOO_LARGE",
        {"part": part, "limit_mb": limit // (1024 * 1024)},
        f"{part} unpacks to more than {limit // (1024 * 1024)} MB, too large to open safely.",
    )


def open_package(path: Path) -> Package:
    """Open an Office file for reading; the file itself is never written."""
    with path.open("rb") as handle:
        head = handle.read(8)
    if head == _OLE_SIGNATURE:
        raise PackageRefusedError(
            "ENCRYPTED",
            {},
            "The file is password-protected; ask for an unprotected copy.",
        )
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as error:
        raise PackageRefusedError(
            "NOT_A_PACKAGE", {}, "The file is not an Office package."
        ) from error
    with archive:
        infos = archive.infolist()
        if len(infos) > ENTRY_LIMIT:
            raise PackageRefusedError(
                "PART_TOO_LARGE",
                {"part": "(entries)", "limit_mb": TOTAL_LIMIT // (1024 * 1024)},
                f"The file holds more than {ENTRY_LIMIT} parts, too many to open safely.",
            )
        if any(info.flag_bits & 0x1 for info in infos):
            raise PackageRefusedError(
                "ENCRYPTED",
                {},
                "The file is password-protected; ask for an unprotected copy.",
            )
        names = [info.filename for info in infos]
        if _CONTENT_TYPES not in names or len(set(names)) != len(names):
            raise PackageRefusedError(
                "NOT_A_PACKAGE", {}, "The file is not an Office package."
            )
        return Package(path, archive)


def package_problems(package: Package) -> list[str]:
    """Structural faults: unparsable XML, dangling relationships, untyped parts."""
    problems: list[str] = []
    present = set(package.names)
    types = package.xml(_CONTENT_TYPES)
    for name in package.names:
        if name.endswith("/"):
            continue
        if name.endswith((".xml", ".rels")):
            try:
                package.xml(name)
            except PackageRefusedError as refused:
                # A DOCTYPE refuses the file; only broken XML is a fault to report.
                if refused.values.get("reason") == "doctype":
                    raise
                problems.append(f"{name} is not well-formed XML")
                continue
        if name != _CONTENT_TYPES and _type_in(types, name) is None:
            problems.append(f"{name} has no content type")
    for override in types.iter(f"{{{_CT}}}Override"):
        part = override.get("PartName", "").lstrip("/")
        if part not in present:
            problems.append(f"content type override for missing part {part}")
    for rels in [n for n in package.names if n.endswith(".rels")]:
        source = _rels_source(rels)
        try:
            root = package.xml(rels)
        except PackageRefusedError:
            continue
        ids = [rel.get("Id") for rel in root.iter(f"{{{_PR}}}Relationship")]
        if len(ids) != len(set(ids)):
            problems.append(f"{rels} repeats a relationship id")
        for rel in root.iter(f"{{{_PR}}}Relationship"):
            if rel.get("TargetMode") == "External":
                continue
            target = _resolve(source, rel.get("Target", ""))
            if target not in present:
                problems.append(f"{rels} points at missing part {target}")
    return problems
