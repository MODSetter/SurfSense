"""A sheet's list dropdowns (ECMA-376 Part 1, 18.3.1.32), with Excel 2010's x14 form,
which is where Excel keeps a list fed from another sheet."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from lxml import etree

from modules.artifacts.revised_copies.engines.excel_refs import in_range, parse_range

Coord = tuple[int, int]
Area = tuple[Coord, Coord]

_X14 = "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
_XM = "http://schemas.microsoft.com/office/excel/2006/main"
# Only "stop", the default, refuses an entry off the list; "warning" and
# "information" let the user keep it.
_LETS_OTHERS_THROUGH = ("warning", "information")


@dataclass(frozen=True)
class Dropdown:
    """One list rule: its cells, the values it offers, and whether Excel refuses others.

    `values` is None when the list comes from a formula this cannot read, such as INDIRECT.
    """

    areas: tuple[str, ...]
    values: tuple[str, ...] | None
    source: str
    allow_blank: bool
    refuses_others: bool

    def covers(self, coord: Coord) -> bool:
        return any(
            (area := parse_range(ref)) is not None and in_range(coord, area)
            for ref in self.areas
        )

    def allows(self, text: str) -> bool:
        return self.values is None or not self.refuses_others or text in self.values


def dropdowns(
    root: etree._Element, resolve: Callable[[str], tuple[str, ...] | None]
) -> list[Dropdown]:
    """Every list rule on the sheet, in file order, the x14 ones last; `resolve` reads a list
    fed from cells or a name."""
    ns = etree.QName(root).namespace
    found: list[Dropdown] = []
    for rule in root.iter(f"{{{ns}}}dataValidation"):
        formula = rule.findtext(f"{{{ns}}}formula1") or ""
        found += _rule(rule, rule.get("sqref", ""), formula, resolve)
    for rule in root.iter(f"{{{_X14}}}dataValidation"):
        formula = rule.findtext(f"{{{_X14}}}formula1/{{{_XM}}}f") or ""
        found += _rule(rule, rule.findtext(f"{{{_XM}}}sqref") or "", formula, resolve)
    return found


def _rule(
    rule: etree._Element,
    sqref: str,
    formula: str,
    resolve: Callable[[str], tuple[str, ...] | None],
) -> list[Dropdown]:
    if rule.get("type") != "list" or not sqref.split():
        return []
    formula = formula.strip()
    values = literal_list(formula)
    if values is None:
        values = resolve(formula.removeprefix("="))
    return [
        Dropdown(
            areas=tuple(sqref.split()),
            values=values,
            source=formula,
            allow_blank=rule.get("allowBlank") in ("1", "true"),
            refuses_others=rule.get("errorStyle", "stop") not in _LETS_OTHERS_THROUGH,
        )
    ]


def literal_list(formula: str) -> tuple[str, ...] | None:
    """`"Yes,No,N/A"` as its items; None for a formula that names cells instead.

    A doubled quote inside stands for one, as in any Excel string.
    """
    if not (len(formula) >= 2 and formula.startswith('"') and formula.endswith('"')):
        return None
    body = formula[1:-1].replace('""', '"')
    return tuple(item for item in body.split(",") if item.strip())


_SHEET_PREFIX = re.compile(r"^(?:'((?:[^']|'')+)'|([^'!]+))!(.+)$")


def split_reference(reference: str) -> tuple[str | None, str]:
    """A reference's sheet name, None on the rule's own sheet, and its cells."""
    match = _SHEET_PREFIX.match(reference.strip())
    if match is None:
        return None, reference.strip()
    quoted, plain, cells = match.groups()
    return (quoted.replace("''", "'") if quoted else plain), cells
