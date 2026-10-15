"""Cut a copy's ties to other files before LibreOffice opens it.

A DOCX or XLSX can pull another local file into a render through a link, a
field or DDE; a profile key is a second line, not a test. Works on the XML as
text, so every byte it does not change stays as it was.
"""

import re
import shutil
import zipfile
from pathlib import Path

from modules.runtime_packs.office.soffice.errors import OfficeFailed

_INVALID = "about:invalid"
# Any prefix or none: LibreOffice reads elements by namespace, not by prefix.
_P = r"(?:[\w.-]+:)?"
_RELATIONSHIP = re.compile(rf"<{_P}Relationship\b[^>]*>")
_EXTERNAL = re.compile(r"""\bTargetMode\s*=\s*(["'])External\1""")
_TARGET = re.compile(r"""(\sTarget\s*=\s*)(["']).*?\2""")
# Fields whose instruction reads another file or program.
_LINKING_FIELDS = {"INCLUDETEXT", "INCLUDEPICTURE", "LINK", "DDE", "DDEAUTO"}
_FIELD_PARTS = re.compile(
    rf"""<{_P}fldChar\b[^>]*\s{_P}fldCharType\s*=\s*["'](?P<kind>begin|separate|end)["'][^>]*>"""
    rf"""|(?P<open><{_P}instrText\b[^>]*>)(?P<text>.*?)</{_P}instrText>""",
    re.DOTALL,
)
_SIMPLE_FIELD = re.compile(
    rf"""(<{_P}fldSimple\b[^>]*\s{_P}instr\s*=\s*)(["'])(.*?)\2"""
)
_DDE_LINK = re.compile(r"""(\sdde(?:Service|Topic)\s*=\s*)(["']).*?\2""")
_CONNECTION_TARGET = re.compile(
    r"""(\s(?:url|connection|sourceFile)\s*=\s*)(["']).*?\2"""
)


def neutralize_external(copy: Path) -> None:
    """Point every external target at nothing and drop linking field instructions.

    Fields keep their last result. A file that is not a zip is left alone; the
    profile's link settings are all that guard it. A part that is not text
    raises OfficeFailed: LibreOffice never gets a copy left as it was.
    """
    if not zipfile.is_zipfile(copy):
        return
    rewritten = copy.with_name(copy.name + ".neutral")
    with zipfile.ZipFile(copy) as source, zipfile.ZipFile(rewritten, "w") as target:
        for entry in source.infolist():
            data = source.read(entry)
            changed = _neutral_part(entry.filename, data)
            target.writestr(entry, data if changed is None else changed)
    shutil.move(rewritten, copy)


def _neutral_part(name: str, data: bytes) -> bytes | None:
    """The part's new bytes, or None when it has nothing to change."""
    if name.endswith(".rels"):
        rule = _relationships
    elif name.startswith("word/") and name.endswith(".xml"):
        rule = _fields
    elif name.startswith("xl/externalLinks/") and name.endswith(".xml"):
        rule = _dde_links
    elif name == "xl/connections.xml":
        rule = _connections
    else:
        return None
    # XML parts are UTF-8 or, behind a byte order mark, UTF-16.
    encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8"
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError as error:
        raise OfficeFailed(f"{name} is not UTF-8 or UTF-16 text") from error
    new = rule(text)
    return None if new == text else new.encode(encoding)


def _relationships(xml: str) -> str:
    def neutral(match: re.Match[str]) -> str:
        element = match.group(0)
        if not _EXTERNAL.search(element):
            return element
        return _TARGET.sub(rf"\g<1>\g<2>{_INVALID}\g<2>", element)

    return _RELATIONSHIP.sub(neutral, xml)


def _fields(xml: str) -> str:
    xml = _SIMPLE_FIELD.sub(
        lambda m: (
            m.group(0)
            if not _links(m.group(3))
            else f"{m.group(1)}{m.group(2)}{m.group(2)}"
        ),
        xml,
    )
    # Complex fields: an instruction may span several runs, all before `separate`.
    blank: list[tuple[int, int]] = []
    # One entry per open field: its instruction runs, or None once past `separate`.
    stack: list[list[re.Match[str]] | None] = []
    for part in _FIELD_PARTS.finditer(xml):
        kind = part.group("kind")
        if kind == "begin":
            stack.append([])
        elif kind in ("separate", "end"):
            if stack and stack[-1] is not None:
                runs = stack[-1]
                if _links("".join(run.group("text") for run in runs)):
                    blank.extend(run.span("text") for run in runs)
                stack[-1] = None
            if kind == "end" and stack:
                stack.pop()
        elif stack and stack[-1] is not None:
            stack[-1].append(part)
    for start, end in sorted(blank, reverse=True):
        xml = xml[:start] + xml[end:]
    return xml


def _links(instruction: str) -> bool:
    words = instruction.split()
    return bool(words) and words[0].upper() in _LINKING_FIELDS


def _dde_links(xml: str) -> str:
    return _DDE_LINK.sub(r"\g<1>\g<2>\g<2>", xml)


def _connections(xml: str) -> str:
    return _CONNECTION_TARGET.sub(r"\g<1>\g<2>\g<2>", xml)
