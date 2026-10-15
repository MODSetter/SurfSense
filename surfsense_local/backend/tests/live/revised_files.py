"""A revised copy as a live case reads it: a Word file's tracked changes and comments, a workbook cell's number.

Written from the OOXML structure, apart from the engine, so a case never grades
the engine with its own code.
"""

import ast
import io
import operator
import re
import zipfile
from dataclasses import dataclass
from functools import cached_property

from lxml import etree
from openpyxl.utils.cell import range_boundaries
from openpyxl.worksheet.worksheet import Worksheet

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NS = {"w": W}
# The engine's files are trusted, but no customer-shaped XML is read with entities on.
_PARSER = etree.XMLParser(
    resolve_entities=False, load_dtd=False, no_network=True, huge_tree=False
)


@dataclass(frozen=True)
class Marked:
    author: str
    text: str


class RedlinedWord:
    def __init__(self, data: bytes) -> None:
        self.data = data

    @cached_property
    def _body(self) -> etree._Element:
        return self._part("word/document.xml")

    @property
    def insertions(self) -> list[Marked]:
        return [
            Marked(_author(e), _text(e, "w:t")) for e in self._body.iter(f"{{{W}}}ins")
        ]

    @property
    def deletions(self) -> list[Marked]:
        return [
            Marked(_author(e), _text(e, "w:delText"))
            for e in self._body.iter(f"{{{W}}}del")
        ]

    @property
    def comments(self) -> list[Marked]:
        with zipfile.ZipFile(io.BytesIO(self.data)) as package:
            if "word/comments.xml" not in package.namelist():
                return []
        part = self._part("word/comments.xml")
        return [
            Marked(_author(c), _text(c, "w:t")) for c in part.iter(f"{{{W}}}comment")
        ]

    @property
    def paragraphs(self) -> list[str]:
        """The body's non-empty paragraphs as they read now: insertions in, deletions out."""
        texts = (_text(p, "w:t") for p in self._body.iter(f"{{{W}}}p"))
        return [t for t in texts if t.strip()]

    def _part(self, name: str) -> etree._Element:
        with zipfile.ZipFile(io.BytesIO(self.data)) as package:
            return etree.fromstring(package.read(name), _PARSER)


def _author(element: etree._Element) -> str:
    return element.get(f"{{{W}}}author", "")


def _text(element: etree._Element, tag: str) -> str:
    return "".join(t.text or "" for t in element.xpath(f".//{tag}", namespaces=_NS))


_SUM = re.compile(r"SUM\(\s*([A-Z]+\d+)\s*:\s*([A-Z]+\d+)\s*\)", re.IGNORECASE)
_FUNCTION = re.compile(r"([A-Z]+)\(", re.IGNORECASE)
_REF = re.compile(r"\$?([A-Z]+)\$?(\d+)", re.IGNORECASE)
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def cell_number(sheet: Worksheet, ref: str) -> float:
    """A cell's number: its value, or its formula worked out from +, -, *, / and SUM over this sheet."""
    value = sheet[ref].value
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{sheet.title}!{ref} holds {value!r}, not a number")
    if isinstance(value, int | float):
        return value
    formula = str(value)
    if not formula.startswith("="):
        raise ValueError(f"{sheet.title}!{ref} holds the text {formula!r}")
    expression = _SUM.sub(lambda m: f"({_sum(sheet, m[1], m[2])})", formula[1:])
    unknown = _FUNCTION.search(expression)
    if unknown:
        raise ValueError(
            f"{sheet.title}!{ref}: cannot work out {unknown[1]} in {formula}"
        )
    expression = _REF.sub(lambda m: f"({cell_number(sheet, m[1] + m[2])})", expression)
    return _arithmetic(ast.parse(expression, mode="eval").body)


def _sum(sheet: Worksheet, first: str, last: str) -> float:
    low_col, low_row, high_col, high_row = range_boundaries(f"{first}:{last}")
    return sum(
        cell_number(sheet, cell.coordinate)
        for row in sheet.iter_rows(low_row, high_row, low_col, high_col)
        for cell in row
        if cell.value is not None
    )


def _arithmetic(node: ast.expr) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_arithmetic(node.operand)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](
            _arithmetic(node.left), _arithmetic(node.right)
        )
    raise ValueError(f"cannot work out {ast.unparse(node)}")
