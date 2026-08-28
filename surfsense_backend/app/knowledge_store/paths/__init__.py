"""The store's path vocabulary.

* :mod:`layout` — on-disk repo and working-copy locations.
* :mod:`store_path` — the ``/documents`` namespace as a value object.
* :mod:`naming` — sanitize text; allocate fresh paths.
* :mod:`resolve` — a stored path back to its ``Document`` row.
* :mod:`legacy` — ``kb_postgres`` title->path derivation, until the cut.

Callers import from here; the submodules are internal.
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
    parse_documents_path,
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
    KEEP_FILE,
    PATH_MARKER,
    StorePath,
    StorePathError,
    recorded_virtual_path,
)

__all__ = [
    "DOCUMENTS_ROOT",
    "KEEP_FILE",
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
    "recorded_virtual_path",
    "safe_filename",
    "safe_folder_segment",
    "to_store_path",
    "to_virtual_path",
    "virtual_path_of",
    "virtual_path_to_doc",
    "working_copies_root",
    "workspace_store_path",
    "workspace_working_copies_path",
]
