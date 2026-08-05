"""The store's path vocabulary: on-disk layout and the ``/documents`` namespace.

Four concerns, one per module, so the legacy quarantine is a file that gets
deleted at the Phase 5 cut rather than lines threaded through the rest:

* :mod:`layout` — where a workspace's repo and working copies live on disk.
* :mod:`store_path` — the ``/documents`` namespace as a validated value object.
* :mod:`naming` — how text becomes a path-safe segment or filename.
* :mod:`resolve` — a stored path back to its ``Document`` row.
* :mod:`legacy` — title->path derivation for ``kb_postgres``, until the cut.

Callers import from ``app.knowledge_store.paths``; the internals are private.
"""

from __future__ import annotations

from app.knowledge_store.paths.layout import (
    working_copies_root,
    workspace_store_path,
    workspace_working_copies_path,
)
from app.knowledge_store.paths.legacy import (
    PathIndex,
    build_path_index,
    doc_to_virtual_path,
    parse_doc_id_suffix,
    safe_filename,
    to_store_path,
    to_virtual_path,
    virtual_path_of,
)
from app.knowledge_store.paths.naming import (
    allocate_path,
    markdown_name_for_source,
    normalize_filename,
    safe_folder_segment,
)
from app.knowledge_store.paths.resolve import virtual_path_to_doc
from app.knowledge_store.paths.store_path import (
    DOCUMENTS_ROOT,
    PATH_MARKER,
    StorePath,
    StorePathError,
    parse_documents_path,
)

__all__ = [
    "DOCUMENTS_ROOT",
    "PATH_MARKER",
    "PathIndex",
    "StorePath",
    "StorePathError",
    "allocate_path",
    "build_path_index",
    "doc_to_virtual_path",
    "markdown_name_for_source",
    "normalize_filename",
    "parse_doc_id_suffix",
    "parse_documents_path",
    "safe_filename",
    "safe_folder_segment",
    "to_store_path",
    "to_virtual_path",
    "virtual_path_of",
    "virtual_path_to_doc",
    "workspace_store_path",
    "workspace_working_copies_path",
    "working_copies_root",
]
