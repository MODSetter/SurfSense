import json
from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

# Levels below a root's own folder, which is depth 0. Hosted's number.
MAX_DEPTH = 8


def depth(session: Session, folder_id: int) -> int:
    """How far below its root folder a folder sits; the root folder is 0."""
    return session.execute(
        text(
            "WITH RECURSIVE up(id, parent_id, depth) AS ("
            "  SELECT id, parent_id, 0 FROM folders WHERE id = :id"
            "  UNION ALL"
            "  SELECT f.id, f.parent_id, up.depth + 1 FROM folders f"
            "  JOIN up ON f.id = up.parent_id"
            ") SELECT max(depth) FROM up WHERE parent_id IS NULL"
        ),
        {"id": folder_id},
    ).scalar_one()


def height(session: Session, folder_id: int) -> int:
    """How many levels hang below a folder; 0 for one with no subfolders."""
    return session.execute(
        text(
            "WITH RECURSIVE down(id, level) AS ("
            "  SELECT id, 0 FROM folders WHERE id = :id"
            "  UNION ALL"
            "  SELECT f.id, down.level + 1 FROM folders f"
            "  JOIN down ON f.parent_id = down.id"
            ") SELECT max(level) FROM down"
        ),
        {"id": folder_id},
    ).scalar_one()


def is_within(session: Session, folder_id: int, ancestor_id: int) -> bool:
    """Whether `folder_id` is `ancestor_id` or below it: a move there is a cycle."""
    return bool(
        session.execute(
            text(
                "WITH RECURSIVE up(id, parent_id) AS ("
                "  SELECT id, parent_id FROM folders WHERE id = :id"
                "  UNION ALL"
                "  SELECT f.id, f.parent_id FROM folders f JOIN up ON f.id = up.parent_id"
                ") SELECT EXISTS (SELECT 1 FROM up WHERE id = :ancestor)"
            ),
            {"id": folder_id, "ancestor": ancestor_id},
        ).scalar_one()
    )


def subtree_ids(session: Session, folder_ids: Iterable[int]) -> list[int]:
    """The folders named and every folder below them."""
    return list(
        session.execute(
            text(
                "WITH RECURSIVE down(id) AS ("
                "  SELECT value FROM json_each(:ids)"
                "  UNION"
                "  SELECT f.id FROM folders f JOIN down ON f.parent_id = down.id"
                ") SELECT id FROM down"
            ),
            {"ids": json.dumps(list(folder_ids))},
        ).scalars()
    )
