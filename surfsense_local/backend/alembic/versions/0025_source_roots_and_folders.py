"""Give every workspace a Library of folders, and every source a folder in it.

Each workspace gets one managed root named "Library" and its root folder. Every
FILE and NOTE goes into that root folder, or, when a cloud import recorded a
`folder_path`, into a chain of folders built from it. Segments differing only in
case or Unicode normalization merge into one folder, and segments past depth 8
are joined with " / " into the eighth, as an upload of a deep tree does.
Artifacts stay unfiled.

`documents` gains `folder_id` by a plain ALTER TABLE, never batch mode: a batch
rebuild drops the table, and with foreign keys on that cascades to every chunk.
The dedup index becomes per folder by DROP and CREATE INDEX; it is weaker than
the old one, so no existing row can violate it. `content_hash` takes the
`dedup_key`, the SHA-256 of a file's bytes, where it was never written.

The folding and clamping rules are written out here rather than imported, so
this revision means the same thing whatever the app's own copy later becomes.

Revision ID: 0025
Revises: 0024
"""

import json
import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025"
down_revision: str | Sequence[str] | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIBRARY = "Library"
MAX_DEPTH = 8
MAX_NAME = 255


def upgrade() -> None:
    _create_tables()
    # Inline, because Alembic will not add a constraint to a SQLite table and
    # SQLite accepts a reference on an added column only in the column itself.
    op.execute(
        "ALTER TABLE documents ADD COLUMN folder_id INTEGER "
        "CONSTRAINT fk_documents_folder_id_folders "
        "REFERENCES folders (id) ON DELETE SET NULL"
    )
    op.create_index("documents_folder", "documents", ["folder_id"])
    _file_every_source(op.get_bind())
    op.execute(
        "UPDATE documents SET content_hash = dedup_key "
        "WHERE content_hash IS NULL AND dedup_key IS NOT NULL"
    )
    op.drop_index("documents_workspace_dedup_key", table_name="documents")
    op.create_index(
        "documents_folder_dedup_key",
        "documents",
        ["workspace_id", "folder_id", "dedup_key"],
        unique=True,
        sqlite_where=sa.text("dedup_key IS NOT NULL"),
    )


def _create_tables() -> None:
    op.create_table(
        "source_roots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "managed",
                "linked",
                name="sourcerootkind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("name_key", sa.String(), nullable=False),
        sa.Column("disk_path", sa.String(), nullable=True),
        sa.Column(
            "state",
            sa.Enum(
                "ready",
                "scanning",
                "unavailable",
                "paused",
                "unlinking",
                name="sourcerootstate",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_source_roots_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_roots")),
    )
    op.create_index(
        "source_roots_workspace_name",
        "source_roots",
        ["workspace_id", "name_key"],
        unique=True,
    )
    op.create_index(
        "source_roots_one_managed",
        "source_roots",
        ["workspace_id"],
        unique=True,
        sqlite_where=sa.text("kind = 'managed'"),
    )

    op.create_table(
        "folders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("root_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("name_key", sa.String(), nullable=False),
        sa.Column("disk_name", sa.String(), nullable=True),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column(
            "state",
            sa.Enum(
                "ready",
                "placeholder",
                "trashed",
                "deleting",
                name="folderstate",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "trash_kind",
            sa.Enum(
                "folder",
                "documents",
                name="trashkind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("trashed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_folders_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["root_id"],
            ["source_roots.id"],
            name=op.f("fk_folders_root_id_source_roots"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["folders.id"],
            name=op.f("fk_folders_parent_id_folders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_folders")),
    )
    op.create_index("folders_root", "folders", ["root_id"])
    op.create_index("folders_workspace", "folders", ["workspace_id"])
    op.create_index(
        "folders_sibling_name",
        "folders",
        ["parent_id", "name_key"],
        unique=True,
        sqlite_where=sa.text(
            "parent_id IS NOT NULL AND state IN ('ready', 'placeholder')"
        ),
    )
    op.create_index(
        "folders_one_root_folder",
        "folders",
        ["root_id"],
        unique=True,
        sqlite_where=sa.text("parent_id IS NULL"),
    )


def _name_key(name: str) -> str:
    # The Library is case-insensitive, and SQLite's NOCASE folds ASCII only.
    return unicodedata.normalize("NFC", name).casefold()


def _segments(folder_path: object) -> list[str]:
    if not isinstance(folder_path, str):
        return []
    parts = [part.strip() for part in folder_path.split("/") if part.strip()]
    if len(parts) > MAX_DEPTH:
        parts = [*parts[: MAX_DEPTH - 1], " / ".join(parts[MAX_DEPTH - 1 :])]
    return [part[:MAX_NAME] for part in parts]


def _file_every_source(bind: sa.Connection) -> None:
    workspace_ids = bind.execute(sa.text("SELECT id FROM workspaces")).scalars().all()
    for workspace_id in workspace_ids:
        root_folder = _library_root_folder(bind, workspace_id)
        root_id = bind.execute(
            sa.text("SELECT root_id FROM folders WHERE id = :id"), {"id": root_folder}
        ).scalar_one()
        known: dict[tuple[int, str], int] = {}
        rows = bind.execute(
            sa.text(
                "SELECT id, document_metadata FROM documents "
                "WHERE workspace_id = :ws AND folder_id IS NULL "
                "AND document_type IN ('FILE', 'NOTE')"
            ),
            {"ws": workspace_id},
        ).all()
        placements: list[dict[str, int]] = []
        for document_id, raw_metadata in rows:
            metadata = (
                json.loads(raw_metadata)
                if isinstance(raw_metadata, str)
                else raw_metadata or {}
            )
            folder_id = root_folder
            for segment in _segments((metadata or {}).get("folder_path")):
                folder_id = _child(
                    bind, known, workspace_id, root_id, folder_id, segment
                )
            placements.append({"id": document_id, "folder": folder_id})
        if placements:
            bind.execute(
                sa.text("UPDATE documents SET folder_id = :folder WHERE id = :id"),
                placements,
            )


def _library_root_folder(bind: sa.Connection, workspace_id: int) -> int:
    root_id = bind.execute(
        sa.text(
            "SELECT id FROM source_roots WHERE workspace_id = :ws AND kind = 'managed'"
        ),
        {"ws": workspace_id},
    ).scalar()
    if root_id is None:
        root_id = bind.execute(
            sa.text(
                "INSERT INTO source_roots(workspace_id, kind, name, name_key, state) "
                "VALUES (:ws, 'managed', :name, :key, 'ready') RETURNING id"
            ),
            {"ws": workspace_id, "name": LIBRARY, "key": _name_key(LIBRARY)},
        ).scalar_one()
    folder_id = bind.execute(
        sa.text("SELECT id FROM folders WHERE root_id = :root AND parent_id IS NULL"),
        {"root": root_id},
    ).scalar()
    if folder_id is None:
        folder_id = bind.execute(
            sa.text(
                "INSERT INTO folders(workspace_id, root_id, name, name_key, state) "
                "VALUES (:ws, :root, :name, :key, 'ready') RETURNING id"
            ),
            {
                "ws": workspace_id,
                "root": root_id,
                "name": LIBRARY,
                "key": _name_key(LIBRARY),
            },
        ).scalar_one()
    return folder_id


def _child(
    bind: sa.Connection,
    known: dict[tuple[int, str], int],
    workspace_id: int,
    root_id: int,
    parent_id: int,
    name: str,
) -> int:
    key = (parent_id, _name_key(name))
    if key in known:
        return known[key]
    folder_id = bind.execute(
        sa.text(
            "SELECT id FROM folders WHERE parent_id = :parent AND name_key = :key "
            "AND state IN ('ready', 'placeholder')"
        ),
        {"parent": parent_id, "key": key[1]},
    ).scalar()
    if folder_id is None:
        folder_id = bind.execute(
            sa.text(
                "INSERT INTO folders(workspace_id, root_id, parent_id, name, "
                "name_key, state) VALUES (:ws, :root, :parent, :name, :key, 'ready') "
                "RETURNING id"
            ),
            {
                "ws": workspace_id,
                "root": root_id,
                "parent": parent_id,
                "name": name,
                "key": key[1],
            },
        ).scalar_one()
    known[key] = folder_id
    return folder_id


def downgrade() -> None:
    op.drop_index("documents_folder_dedup_key", table_name="documents")
    # The old index is per workspace: a twin filed in a second folder keeps its
    # row and loses only its dedup key.
    op.execute(
        "UPDATE documents SET dedup_key = NULL WHERE dedup_key IS NOT NULL "
        "AND id NOT IN (SELECT min(id) FROM documents WHERE dedup_key IS NOT NULL "
        "GROUP BY workspace_id, dedup_key)"
    )
    op.create_index(
        "documents_workspace_dedup_key",
        "documents",
        ["workspace_id", "dedup_key"],
        unique=True,
        sqlite_where=sa.text("dedup_key IS NOT NULL"),
    )
    op.drop_index("documents_folder", table_name="documents")
    op.execute("ALTER TABLE documents DROP COLUMN folder_id")
    op.drop_index("folders_one_root_folder", table_name="folders")
    op.drop_index("folders_sibling_name", table_name="folders")
    op.drop_index("folders_workspace", table_name="folders")
    op.drop_index("folders_root", table_name="folders")
    op.drop_table("folders")
    op.drop_index("source_roots_one_managed", table_name="source_roots")
    op.drop_index("source_roots_workspace_name", table_name="source_roots")
    op.drop_table("source_roots")
