"""Which cells a protected sheet keeps locked (ECMA-376 Part 1, 18.3.1.85 and 18.8.33).

A cell is locked unless its style says otherwise, and the lock holds only
while its sheet is protected.
"""

from __future__ import annotations

from lxml import etree


def sheet_protected(root: etree._Element) -> bool:
    ns = etree.QName(root).namespace
    protection = root.find(f"{{{ns}}}sheetProtection")
    return protection is not None and protection.get("sheet") in ("1", "true")


def unlocked_styles(styles: etree._Element | None) -> frozenset[int]:
    """The cell styles (`cellXfs` indexes) whose cells stay editable on a protected sheet."""
    if styles is None:
        return frozenset()
    ns = etree.QName(styles).namespace
    xfs = styles.find(f"{{{ns}}}cellXfs")
    if xfs is None:
        return frozenset()
    return frozenset(
        index
        for index, xf in enumerate(xfs.findall(f"{{{ns}}}xf"))
        if (protection := xf.find(f"{{{ns}}}protection")) is not None
        and protection.get("locked") in ("0", "false")
    )
