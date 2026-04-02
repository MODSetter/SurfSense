"""
Local folder indexer.

Indexes files from a local folder on disk. Supports:
- Full-scan mode (startup reconciliation / manual trigger)
- Single-file mode (chokidar real-time trigger)
- Filesystem folder structure mirroring into DB Folder rows
- Document versioning via create_version_snapshot
- ETL-based file parsing for binary formats (PDF, DOCX, images, audio, etc.)

Desktop-only: all change detection is driven by chokidar in the desktop app.
Config (folder_path, exclude_patterns, etc.) is passed in from the caller —
no connector row is read.
"""

import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    Document,
    DocumentStatus,
    DocumentType,
    Folder,
)
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_hashing import compute_identifier_hash
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_versioning import create_version_snapshot

from .base import (
    check_document_by_unique_identifier,
    logger,
)

PLAINTEXT_EXTENSIONS = frozenset({
    ".md", ".markdown", ".txt", ".text", ".csv", ".tsv",
    ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".xml", ".html", ".htm", ".css", ".scss", ".less", ".sass",
    ".py", ".pyw", ".pyi", ".pyx",
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".java", ".kt", ".kts", ".scala", ".groovy",
    ".c", ".h", ".cpp", ".cxx", ".cc", ".hpp", ".hxx",
    ".cs", ".fs", ".fsx",
    ".go", ".rs", ".rb", ".php", ".pl", ".pm", ".lua",
    ".swift", ".m", ".mm",
    ".r", ".R", ".jl",
    ".sh", ".bash", ".zsh", ".fish", ".bat", ".cmd", ".ps1",
    ".sql", ".graphql", ".gql",
    ".env", ".gitignore", ".dockerignore", ".editorconfig",
    ".makefile", ".cmake",
    ".log", ".rst", ".tex", ".bib", ".org", ".adoc", ".asciidoc",
    ".vue", ".svelte", ".astro",
    ".tf", ".hcl", ".proto",
})

AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm",
})


def _is_plaintext_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in PLAINTEXT_EXTENSIONS


def _is_audio_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in AUDIO_EXTENSIONS


def _needs_etl(filename: str) -> bool:
    """File is not plaintext and not audio — requires ETL service to parse."""
    return not _is_plaintext_file(filename) and not _is_audio_file(filename)

HeartbeatCallbackType = Callable[[int], Awaitable[None]]

DEFAULT_EXCLUDE_PATTERNS = [
    ".git",
    "node_modules",
    "__pycache__",
    ".DS_Store",
    ".obsidian",
    ".trash",
]


def scan_folder(
    folder_path: str,
    file_extensions: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> list[dict]:
    """Walk a directory and return a list of file entries.

    Args:
        folder_path: Absolute path to the folder to scan.
        file_extensions: If provided, only include files with these extensions
            (e.g. [".md", ".txt"]). ``None`` means include all files.
        exclude_patterns: Directory/file names to exclude.  Any path component
            matching one of these strings is skipped.

    Returns:
        List of dicts with keys: path, relative_path, name, modified_at, size.
    """
    root = Path(folder_path)
    if not root.exists():
        raise ValueError(f"Folder path does not exist: {folder_path}")

    if exclude_patterns is None:
        exclude_patterns = []

    files: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)

        dirnames[:] = [
            d for d in dirnames if d not in exclude_patterns
        ]

        if any(part in exclude_patterns for part in rel_dir.parts):
            continue

        for fname in filenames:
            if fname in exclude_patterns:
                continue

            full = Path(dirpath) / fname

            if file_extensions is not None:
                if full.suffix.lower() not in file_extensions:
                    continue

            try:
                stat = full.stat()
                rel_path = full.relative_to(root)
                files.append(
                    {
                        "path": str(full),
                        "relative_path": str(rel_path),
                        "name": full.name,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                        "size": stat.st_size,
                    }
                )
            except OSError as e:
                logger.warning(f"Could not stat file {full}: {e}")

    return files


def _read_plaintext_file(file_path: str) -> str:
    """Read a plaintext/text-based file as UTF-8."""
    with open(file_path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    if "\x00" in content:
        raise ValueError(
            f"File contains null bytes — likely a binary file opened as text: {file_path}"
        )
    return content


async def _read_file_content(file_path: str, filename: str) -> str:
    """Read file content, using ETL for binary formats.

    Plaintext files are read directly. Audio and document files (PDF, DOCX, etc.)
    are routed through the configured ETL service (same as Google Drive / OneDrive).

    Raises ValueError if the file cannot be parsed (e.g. no ETL service configured
    for a binary file).
    """
    if _is_plaintext_file(filename):
        return _read_plaintext_file(file_path)

    if _is_audio_file(filename):
        etl_service = config.ETL_SERVICE if hasattr(config, "ETL_SERVICE") else None
        stt_service_val = config.STT_SERVICE if hasattr(config, "STT_SERVICE") else None
        if not stt_service_val and not etl_service:
            raise ValueError(
                f"No STT_SERVICE configured — cannot transcribe audio file: {filename}"
            )

    if _needs_etl(filename):
        etl_service = getattr(config, "ETL_SERVICE", None)
        if not etl_service:
            raise ValueError(
                f"No ETL_SERVICE configured — cannot parse binary file: {filename}. "
                f"Set ETL_SERVICE to UNSTRUCTURED, LLAMACLOUD, or DOCLING in your .env"
            )

    from app.connectors.onedrive.content_extractor import (
        _parse_file_to_markdown,
    )

    return await _parse_file_to_markdown(file_path, filename)


def _content_hash(content: str, search_space_id: int) -> str:
    """SHA-256 hash of content scoped to a search space.

    Matches the format used by ``compute_content_hash`` in the unified
    pipeline so that dedup checks are consistent.
    """
    import hashlib
    return hashlib.sha256(f"{search_space_id}:{content}".encode("utf-8")).hexdigest()


async def _compute_file_content_hash(
    file_path: str, filename: str, search_space_id: int,
) -> tuple[str, str]:
    """Read a file (via ETL if needed) and compute its content hash.

    Returns (content_text, content_hash).
    """
    content = await _read_file_content(file_path, filename)
    return content, _content_hash(content, search_space_id)


async def _mirror_folder_structure(
    session: AsyncSession,
    folder_path: str,
    folder_name: str,
    search_space_id: int,
    user_id: str,
    root_folder_id: int | None = None,
    exclude_patterns: list[str] | None = None,
) -> tuple[dict[str, int], int]:
    """Mirror the local filesystem directory structure into DB Folder rows.

    Returns (mapping, root_folder_id) where mapping is
    relative_dir_path -> folder_id. The empty string key maps to the root folder.
    """
    root = Path(folder_path)
    if exclude_patterns is None:
        exclude_patterns = []

    subdirs: list[str] = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_patterns]
        rel = Path(dirpath).relative_to(root)
        if any(part in exclude_patterns for part in rel.parts):
            continue
        rel_str = str(rel) if str(rel) != "." else ""
        if rel_str:
            subdirs.append(rel_str)

    subdirs.sort(key=lambda p: p.count(os.sep))

    mapping: dict[str, int] = {}

    if root_folder_id:
        existing = (
            await session.execute(
                select(Folder).where(Folder.id == root_folder_id)
            )
        ).scalar_one_or_none()
        if existing:
            mapping[""] = existing.id
        else:
            root_folder_id = None

    if not root_folder_id:
        root_folder = Folder(
            name=folder_name,
            search_space_id=search_space_id,
            created_by_id=user_id,
            position="a0",
        )
        session.add(root_folder)
        await session.flush()
        mapping[""] = root_folder.id
        root_folder_id = root_folder.id

    for rel_dir in subdirs:
        dir_parts = Path(rel_dir).parts
        dir_name = dir_parts[-1]
        parent_rel = str(Path(*dir_parts[:-1])) if len(dir_parts) > 1 else ""

        parent_id = mapping.get(parent_rel, mapping[""])

        existing_folder = (
            await session.execute(
                select(Folder).where(
                    Folder.name == dir_name,
                    Folder.parent_id == parent_id,
                    Folder.search_space_id == search_space_id,
                )
            )
        ).scalar_one_or_none()

        if existing_folder:
            mapping[rel_dir] = existing_folder.id
        else:
            new_folder = Folder(
                name=dir_name,
                parent_id=parent_id,
                search_space_id=search_space_id,
                created_by_id=user_id,
                position="a0",
            )
            session.add(new_folder)
            await session.flush()
            mapping[rel_dir] = new_folder.id

    await session.flush()
    return mapping, root_folder_id


async def _resolve_folder_for_file(
    session: AsyncSession,
    rel_path: str,
    root_folder_id: int,
    search_space_id: int,
    user_id: str,
) -> int:
    """Given a file's relative path, ensure all parent Folder rows exist and
    return the folder_id for the file's immediate parent directory.

    For a file at "notes/daily/today.md", this ensures Folder rows exist for
    "notes" and "notes/daily", and returns the id of "notes/daily".
    For a file at "readme.md" (root level), returns root_folder_id.
    """
    parent_dir = str(Path(rel_path).parent)
    if parent_dir == ".":
        return root_folder_id

    parts = Path(parent_dir).parts
    current_parent_id = root_folder_id

    for part in parts:
        existing = (
            await session.execute(
                select(Folder).where(
                    Folder.name == part,
                    Folder.parent_id == current_parent_id,
                    Folder.search_space_id == search_space_id,
                )
            )
        ).scalar_one_or_none()

        if existing:
            current_parent_id = existing.id
        else:
            new_folder = Folder(
                name=part,
                parent_id=current_parent_id,
                search_space_id=search_space_id,
                created_by_id=user_id,
                position="a0",
            )
            session.add(new_folder)
            await session.flush()
            current_parent_id = new_folder.id

    return current_parent_id


async def _cleanup_empty_folder_chain(
    session: AsyncSession,
    folder_id: int,
    root_folder_id: int,
) -> None:
    """Walk up from folder_id toward root, deleting empty folders (no docs, no
    children). Stops at root_folder_id which is never deleted."""
    current_id = folder_id
    while current_id and current_id != root_folder_id:
        has_doc = (
            await session.execute(
                select(Document.id).where(Document.folder_id == current_id).limit(1)
            )
        ).scalar_one_or_none()
        if has_doc is not None:
            break

        has_child = (
            await session.execute(
                select(Folder.id).where(Folder.parent_id == current_id).limit(1)
            )
        ).scalar_one_or_none()
        if has_child is not None:
            break

        folder = (
            await session.execute(select(Folder).where(Folder.id == current_id))
        ).scalar_one_or_none()
        if not folder:
            break

        parent_id = folder.parent_id
        await session.delete(folder)
        await session.flush()
        current_id = parent_id


async def _cleanup_empty_folders(
    session: AsyncSession,
    root_folder_id: int,
    search_space_id: int,
    existing_dirs_on_disk: set[str],
    folder_mapping: dict[str, int],
) -> None:
    """Delete Folder rows that are empty (no docs, no children) and no longer on disk."""
    from sqlalchemy import delete as sa_delete

    id_to_rel: dict[int, str] = {fid: rel for rel, fid in folder_mapping.items() if rel}

    all_folders = (
        await session.execute(
            select(Folder).where(
                Folder.search_space_id == search_space_id,
                Folder.id != root_folder_id,
            )
        )
    ).scalars().all()

    candidates: list[Folder] = []
    for folder in all_folders:
        rel = id_to_rel.get(folder.id)
        if rel and rel in existing_dirs_on_disk:
            continue
        candidates.append(folder)

    changed = True
    while changed:
        changed = False
        remaining: list[Folder] = []
        for folder in candidates:
            doc_exists = (
                await session.execute(
                    select(Document.id).where(Document.folder_id == folder.id).limit(1)
                )
            ).scalar_one_or_none()
            if doc_exists is not None:
                remaining.append(folder)
                continue

            child_exists = (
                await session.execute(
                    select(Folder.id).where(Folder.parent_id == folder.id).limit(1)
                )
            ).scalar_one_or_none()
            if child_exists is not None:
                remaining.append(folder)
                continue

            await session.execute(sa_delete(Folder).where(Folder.id == folder.id))
            changed = True
        candidates = remaining


def _build_connector_doc(
    title: str,
    content: str,
    relative_path: str,
    folder_name: str,
    *,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
) -> ConnectorDocument:
    """Build a ConnectorDocument from a local file's extracted content."""
    unique_id = f"{folder_name}:{relative_path}"
    metadata = {
        "folder_name": folder_name,
        "file_path": relative_path,
        "document_type": "Local Folder File",
        "connector_type": "Local Folder",
    }
    fallback_summary = f"File: {title}\n\n{content[:4000]}"

    return ConnectorDocument(
        title=title,
        source_markdown=content,
        unique_id=unique_id,
        document_type=DocumentType.LOCAL_FOLDER_FILE,
        search_space_id=search_space_id,
        connector_id=None,
        created_by_id=user_id,
        should_summarize=enable_summary,
        fallback_summary=fallback_summary,
        metadata=metadata,
    )


async def index_local_folder(
    session: AsyncSession,
    search_space_id: int,
    user_id: str,
    folder_path: str,
    folder_name: str,
    exclude_patterns: list[str] | None = None,
    file_extensions: list[str] | None = None,
    root_folder_id: int | None = None,
    enable_summary: bool = False,
    target_file_path: str | None = None,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int, int | None, str | None]:
    """Index files from a local folder.

    Supports two modes:
    - Full scan (target_file_path=None): walks entire folder, handles new/changed/deleted files.
    - Single-file (target_file_path set): processes only that file.

    Returns (indexed_count, skipped_count, root_folder_id, error_or_warning_message).
    """
    task_logger = TaskLoggingService(session, search_space_id)

    log_entry = await task_logger.log_task_start(
        task_name="local_folder_indexing",
        source="local_folder_indexing_task",
        message=f"Starting local folder indexing for {folder_name}",
        metadata={
            "folder_path": folder_path,
            "user_id": str(user_id),
            "target_file_path": target_file_path,
        },
    )

    try:
        if not folder_path or not os.path.exists(folder_path):
            await task_logger.log_task_failure(
                log_entry,
                f"Folder path missing or does not exist: {folder_path}",
                "Folder not found",
                {},
            )
            return 0, 0, root_folder_id, f"Folder path missing or does not exist: {folder_path}"

        if exclude_patterns is None:
            exclude_patterns = DEFAULT_EXCLUDE_PATTERNS

        # ====================================================================
        # SINGLE-FILE MODE
        # ====================================================================
        if target_file_path:
            indexed, skipped, err = await _index_single_file(
                session=session,
                search_space_id=search_space_id,
                user_id=user_id,
                folder_path=folder_path,
                folder_name=folder_name,
                target_file_path=target_file_path,
                enable_summary=enable_summary,
                root_folder_id=root_folder_id,
                task_logger=task_logger,
                log_entry=log_entry,
            )
            return indexed, skipped, root_folder_id, err

        # ====================================================================
        # FULL-SCAN MODE
        # ====================================================================

        await task_logger.log_task_progress(
            log_entry, "Mirroring folder structure", {"stage": "folder_mirror"}
        )

        folder_mapping, root_folder_id = await _mirror_folder_structure(
            session=session,
            folder_path=folder_path,
            folder_name=folder_name,
            search_space_id=search_space_id,
            user_id=user_id,
            root_folder_id=root_folder_id,
            exclude_patterns=exclude_patterns,
        )
        await session.flush()

        try:
            files = scan_folder(folder_path, file_extensions, exclude_patterns)
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry, f"Failed to scan folder: {e}", "Scan error", {}
            )
            return 0, 0, root_folder_id, f"Failed to scan folder: {e}"

        logger.info(f"Found {len(files)} files in folder")

        indexed_count = 0
        skipped_count = 0
        failed_count = 0

        # ================================================================
        # PHASE 1: Pre-filter files (mtime / content-hash), version changed
        # ================================================================
        connector_docs: list[ConnectorDocument] = []
        # Maps unique_id -> (relative_path, mtime) for post-pipeline folder_id assignment
        file_meta_map: dict[str, dict] = {}
        seen_unique_hashes: set[str] = set()

        for file_info in files:
            try:
                relative_path = file_info["relative_path"]
                file_path_abs = file_info["path"]

                unique_identifier = f"{folder_name}:{relative_path}"
                unique_identifier_hash = compute_identifier_hash(
                    DocumentType.LOCAL_FOLDER_FILE.value,
                    unique_identifier,
                    search_space_id,
                )
                seen_unique_hashes.add(unique_identifier_hash)

                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                if existing_document:
                    stored_mtime = (existing_document.document_metadata or {}).get("mtime")
                    current_mtime = file_info["modified_at"].timestamp()

                    if stored_mtime and abs(current_mtime - stored_mtime) < 1.0:
                        if not DocumentStatus.is_state(
                            existing_document.status, DocumentStatus.READY
                        ):
                            existing_document.status = DocumentStatus.ready()
                        skipped_count += 1
                        continue

                    try:
                        content, content_hash = await _compute_file_content_hash(
                            file_path_abs, file_info["relative_path"], search_space_id
                        )
                    except Exception as read_err:
                        logger.warning(f"Could not read {file_path_abs}: {read_err}")
                        skipped_count += 1
                        continue

                    if existing_document.content_hash == content_hash:
                        meta = dict(existing_document.document_metadata or {})
                        meta["mtime"] = current_mtime
                        existing_document.document_metadata = meta
                        if not DocumentStatus.is_state(
                            existing_document.status, DocumentStatus.READY
                        ):
                            existing_document.status = DocumentStatus.ready()
                        skipped_count += 1
                        continue

                    await create_version_snapshot(session, existing_document)
                else:
                    try:
                        content, content_hash = await _compute_file_content_hash(
                            file_path_abs, file_info["relative_path"], search_space_id
                        )
                    except Exception as read_err:
                        logger.warning(f"Could not read {file_path_abs}: {read_err}")
                        skipped_count += 1
                        continue

                    if not content.strip():
                        skipped_count += 1
                        continue

                doc = _build_connector_doc(
                    title=file_info["name"],
                    content=content,
                    relative_path=relative_path,
                    folder_name=folder_name,
                    search_space_id=search_space_id,
                    user_id=user_id,
                    enable_summary=enable_summary,
                )
                connector_docs.append(doc)
                file_meta_map[unique_identifier] = {
                    "relative_path": relative_path,
                    "mtime": file_info["modified_at"].timestamp(),
                }

            except Exception as e:
                logger.exception(f"Phase 1 error for {file_info.get('path')}: {e}")
                failed_count += 1

        # ================================================================
        # PHASE 1.5: Delete documents no longer on disk
        # ================================================================
        all_root_folder_ids = set(folder_mapping.values())
        all_db_folders = (
            await session.execute(
                select(Folder.id).where(
                    Folder.search_space_id == search_space_id,
                )
            )
        ).scalars().all()
        all_root_folder_ids.update(all_db_folders)

        all_folder_docs = (
            await session.execute(
                select(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == search_space_id,
                    Document.folder_id.in_(list(all_root_folder_ids)),
                )
            )
        ).scalars().all()

        for doc in all_folder_docs:
            if doc.unique_identifier_hash not in seen_unique_hashes:
                await session.delete(doc)

        await session.flush()

        # ================================================================
        # PHASE 2: Index via unified pipeline
        # ================================================================
        if connector_docs:
            from app.indexing_pipeline.document_hashing import (
                compute_unique_identifier_hash,
            )

            pipeline = IndexingPipelineService(session)
            doc_map = {
                compute_unique_identifier_hash(cd): cd for cd in connector_docs
            }
            documents = await pipeline.prepare_for_indexing(connector_docs)

            llm = await get_user_long_context_llm(session, user_id, search_space_id)

            for document in documents:
                connector_doc = doc_map.get(document.unique_identifier_hash)
                if connector_doc is None:
                    failed_count += 1
                    continue

                result = await pipeline.index(document, connector_doc, llm)

                if DocumentStatus.is_state(result.status, DocumentStatus.READY):
                    indexed_count += 1

                    # Assign folder_id and mtime post-pipeline
                    rel_path = (connector_doc.metadata or {}).get("file_path", "")
                    parent_dir = str(Path(rel_path).parent) if rel_path else ""
                    if parent_dir == ".":
                        parent_dir = ""
                    fid = folder_mapping.get(parent_dir, folder_mapping.get(""))

                    unique_id = connector_doc.unique_id
                    mtime_info = file_meta_map.get(unique_id, {})

                    result.folder_id = fid
                    doc_meta = dict(result.document_metadata or {})
                    doc_meta["mtime"] = mtime_info.get("mtime")
                    result.document_metadata = doc_meta
                else:
                    failed_count += 1

                if on_heartbeat_callback and indexed_count % 5 == 0:
                    await on_heartbeat_callback(indexed_count)

        # Cleanup empty folders
        existing_dirs = set()
        for dirpath, dirnames, _ in os.walk(folder_path):
            dirnames[:] = [d for d in dirnames if d not in exclude_patterns]
            rel = str(Path(dirpath).relative_to(folder_path))
            if rel == ".":
                rel = ""
            if rel and not any(part in exclude_patterns for part in Path(rel).parts):
                existing_dirs.add(rel)

        root_fid = folder_mapping.get("")
        if root_fid:
            await _cleanup_empty_folders(
                session, root_fid, search_space_id, existing_dirs, folder_mapping
            )

        try:
            await session.commit()
        except Exception as e:
            if "duplicate key value violates unique constraint" in str(e).lower():
                logger.warning(f"Duplicate key during commit: {e}")
                await session.rollback()
            else:
                raise

        warning_parts = []
        if failed_count > 0:
            warning_parts.append(f"{failed_count} failed")
        warning_message = ", ".join(warning_parts) if warning_parts else None

        await task_logger.log_task_success(
            log_entry,
            f"Completed local folder indexing for {folder_name}",
            {
                "indexed": indexed_count,
                "skipped": skipped_count,
                "failed": failed_count,
            },
        )

        return indexed_count, skipped_count, root_folder_id, warning_message

    except SQLAlchemyError as e:
        logger.exception(f"Database error during local folder indexing: {e}")
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry, f"DB error: {e}", "Database error", {}
        )
        return 0, 0, root_folder_id, f"Database error: {e}"

    except Exception as e:
        logger.exception(f"Error during local folder indexing: {e}")
        await task_logger.log_task_failure(
            log_entry, f"Error: {e}", "Unexpected error", {}
        )
        return 0, 0, root_folder_id, str(e)


async def _index_single_file(
    session: AsyncSession,
    search_space_id: int,
    user_id: str,
    folder_path: str,
    folder_name: str,
    target_file_path: str,
    enable_summary: bool,
    root_folder_id: int | None,
    task_logger,
    log_entry,
) -> tuple[int, int, str | None]:
    """Process a single file (chokidar real-time trigger)."""
    try:
        full_path = Path(target_file_path)
        if not full_path.exists():
            rel = str(full_path.relative_to(folder_path))
            unique_id = f"{folder_name}:{rel}"
            uid_hash = compute_identifier_hash(
                DocumentType.LOCAL_FOLDER_FILE.value, unique_id, search_space_id
            )
            existing = await check_document_by_unique_identifier(session, uid_hash)
            if existing:
                deleted_folder_id = existing.folder_id
                await session.delete(existing)
                await session.flush()
                if deleted_folder_id and root_folder_id:
                    await _cleanup_empty_folder_chain(
                        session, deleted_folder_id, root_folder_id
                    )
                await session.commit()
                return 0, 0, None
            return 0, 0, None

        rel_path = str(full_path.relative_to(folder_path))

        unique_id = f"{folder_name}:{rel_path}"
        uid_hash = compute_identifier_hash(
            DocumentType.LOCAL_FOLDER_FILE.value, unique_id, search_space_id
        )

        try:
            content, content_hash = await _compute_file_content_hash(
                str(full_path), full_path.name, search_space_id
            )
        except Exception as e:
            return 0, 1, f"Could not read file: {e}"

        if not content.strip():
            return 0, 1, None

        existing = await check_document_by_unique_identifier(session, uid_hash)

        if existing:
            if existing.content_hash == content_hash:
                mtime = full_path.stat().st_mtime
                meta = dict(existing.document_metadata or {})
                meta["mtime"] = mtime
                existing.document_metadata = meta
                await session.commit()
                return 0, 1, None

            await create_version_snapshot(session, existing)

        mtime = full_path.stat().st_mtime

        connector_doc = _build_connector_doc(
            title=full_path.name,
            content=content,
            relative_path=rel_path,
            folder_name=folder_name,
            search_space_id=search_space_id,
            user_id=user_id,
            enable_summary=enable_summary,
        )

        pipeline = IndexingPipelineService(session)
        llm = await get_user_long_context_llm(session, user_id, search_space_id)
        documents = await pipeline.prepare_for_indexing([connector_doc])

        if not documents:
            return 0, 1, None

        db_doc = documents[0]
        await pipeline.index(db_doc, connector_doc, llm)

        # Post-pipeline: assign folder_id and mtime
        await session.refresh(db_doc)
        folder_id = None
        if root_folder_id:
            folder_id = await _resolve_folder_for_file(
                session, rel_path, root_folder_id, search_space_id, user_id
            )
        db_doc.folder_id = folder_id
        doc_meta = dict(db_doc.document_metadata or {})
        doc_meta["mtime"] = mtime
        db_doc.document_metadata = doc_meta
        await session.commit()

        indexed = 1 if DocumentStatus.is_state(db_doc.status, DocumentStatus.READY) else 0
        failed_msg = None if indexed else "Indexing failed"

        if indexed:
            await task_logger.log_task_success(
                log_entry,
                f"Single file indexed: {rel_path}",
                {"file": rel_path},
            )
        return indexed, 0 if indexed else 1, failed_msg

    except Exception as e:
        logger.exception(f"Error indexing single file {target_file_path}: {e}")
        await session.rollback()
        return 0, 0, str(e)
