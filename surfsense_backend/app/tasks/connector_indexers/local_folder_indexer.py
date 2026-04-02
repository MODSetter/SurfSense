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
import time
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
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    embed_text,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)
from app.utils.document_versioning import create_version_snapshot

from .base import (
    build_document_metadata_string,
    check_document_by_unique_identifier,
    check_duplicate_document_by_hash,
    get_current_timestamp,
    logger,
    safe_set_chunks,
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
HEARTBEAT_INTERVAL_SECONDS = 30

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


async def _compute_file_content_hash(
    file_path: str, filename: str, search_space_id: int,
) -> tuple[str, str]:
    """Read a file (via ETL if needed) and compute its content hash.

    Returns (content_text, content_hash).
    """
    content = await _read_file_content(file_path, filename)
    content_hash = generate_content_hash(content, search_space_id)
    return content, content_hash


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
        duplicate_count = 0

        last_heartbeat_time = time.time()

        # ================================================================
        # PHASE 1: Analyze all files, create pending documents
        # ================================================================
        files_to_process: list[dict] = []
        new_documents_created = False
        seen_unique_hashes: set[str] = set()

        for file_info in files:
            try:
                relative_path = file_info["relative_path"]
                file_path_abs = file_info["path"]

                unique_identifier = f"{folder_name}:{relative_path}"
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.LOCAL_FOLDER_FILE,
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

                    files_to_process.append(
                        {
                            "document": existing_document,
                            "is_new": False,
                            "file_info": file_info,
                            "content": content,
                            "content_hash": content_hash,
                            "unique_identifier_hash": unique_identifier_hash,
                            "relative_path": relative_path,
                            "title": file_info["name"],
                        }
                    )
                    continue

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

                with session.no_autoflush:
                    dup = await check_duplicate_document_by_hash(session, content_hash)
                if dup:
                    duplicate_count += 1
                    skipped_count += 1
                    continue

                parent_dir = str(Path(relative_path).parent)
                if parent_dir == ".":
                    parent_dir = ""
                folder_id = folder_mapping.get(parent_dir, folder_mapping.get(""))

                document = Document(
                    search_space_id=search_space_id,
                    title=file_info["name"],
                    document_type=DocumentType.LOCAL_FOLDER_FILE,
                    document_metadata={
                        "folder_name": folder_name,
                        "file_path": relative_path,
                        "mtime": file_info["modified_at"].timestamp(),
                    },
                    content="Pending...",
                    content_hash=unique_identifier_hash,
                    unique_identifier_hash=unique_identifier_hash,
                    embedding=None,
                    status=DocumentStatus.pending(),
                    updated_at=get_current_timestamp(),
                    created_by_id=user_id,
                    connector_id=None,
                    folder_id=folder_id,
                )
                session.add(document)
                new_documents_created = True

                files_to_process.append(
                    {
                        "document": document,
                        "is_new": True,
                        "file_info": file_info,
                        "content": content,
                        "content_hash": content_hash,
                        "unique_identifier_hash": unique_identifier_hash,
                        "relative_path": relative_path,
                        "title": file_info["name"],
                    }
                )

            except Exception as e:
                logger.exception(f"Phase 1 error for {file_info.get('path')}: {e}")
                failed_count += 1

        if new_documents_created:
            await session.commit()

        # ================================================================
        # PHASE 1.5: Delete documents no longer on disk
        # ================================================================
        all_folder_docs = (
            await session.execute(
                select(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == search_space_id,
                    Document.folder_id.in_(list(folder_mapping.values())),
                )
            )
        ).scalars().all()

        for doc in all_folder_docs:
            if doc.unique_identifier_hash not in seen_unique_hashes:
                await session.delete(doc)

        await session.flush()

        # ================================================================
        # PHASE 2: Process each document
        # ================================================================
        long_context_llm = await get_user_long_context_llm(
            session, user_id, search_space_id
        )

        for item in files_to_process:
            if on_heartbeat_callback:
                current_time = time.time()
                if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL_SECONDS:
                    await on_heartbeat_callback(indexed_count)
                    last_heartbeat_time = current_time

            document = item["document"]
            try:
                document.status = DocumentStatus.processing()
                await session.commit()

                title = item["title"]
                relative_path = item["relative_path"]
                content = item["content"]
                content_hash = item["content_hash"]
                file_info = item["file_info"]

                metadata_sections = [
                    (
                        "METADATA",
                        [
                            f"Title: {title}",
                            f"Folder: {folder_name}",
                            f"Path: {relative_path}",
                        ],
                    ),
                    ("CONTENT", [content]),
                ]
                document_string = build_document_metadata_string(metadata_sections)

                summary_content = ""
                if long_context_llm and enable_summary:
                    doc_meta = {
                        "folder_name": folder_name,
                        "file_path": relative_path,
                    }
                    summary_content, _ = await generate_document_summary(
                        document_string, long_context_llm, doc_meta
                    )

                embedding = embed_text(document_string)
                chunks = await create_document_chunks(document_string)

                parent_dir = str(Path(relative_path).parent)
                if parent_dir == ".":
                    parent_dir = ""
                folder_id = folder_mapping.get(parent_dir, folder_mapping.get(""))

                document.title = title
                document.content = document_string
                document.content_hash = content_hash
                document.source_markdown = content
                document.embedding = embedding
                document.document_metadata = {
                    "folder_name": folder_name,
                    "file_path": relative_path,
                    "summary": summary_content,
                    "mtime": file_info["modified_at"].timestamp(),
                }
                document.folder_id = folder_id
                await safe_set_chunks(session, document, chunks)
                document.updated_at = get_current_timestamp()
                document.status = DocumentStatus.ready()

                indexed_count += 1

                if indexed_count % 10 == 0:
                    await session.commit()

            except Exception as e:
                logger.exception(f"Phase 2 error for {item.get('relative_path')}: {e}")
                try:
                    await session.rollback()
                except Exception:
                    pass
                try:
                    document.status = DocumentStatus.failed(str(e)[:500])
                    document.updated_at = get_current_timestamp()
                    await session.commit()
                except Exception:
                    try:
                        await session.rollback()
                    except Exception:
                        pass
                failed_count += 1

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
        if duplicate_count > 0:
            warning_parts.append(f"{duplicate_count} duplicate")
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
                "duplicates": duplicate_count,
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
    task_logger,
    log_entry,
) -> tuple[int, int, str | None]:
    """Process a single file (chokidar real-time trigger)."""
    try:
        full_path = Path(target_file_path)
        if not full_path.exists():
            rel = str(full_path.relative_to(folder_path))
            unique_id = f"{folder_name}:{rel}"
            uid_hash = generate_unique_identifier_hash(
                DocumentType.LOCAL_FOLDER_FILE, unique_id, search_space_id
            )
            existing = await check_document_by_unique_identifier(session, uid_hash)
            if existing:
                await session.delete(existing)
                await session.commit()
                return 0, 0, None
            return 0, 0, None

        rel_path = str(full_path.relative_to(folder_path))

        unique_id = f"{folder_name}:{rel_path}"
        uid_hash = generate_unique_identifier_hash(
            DocumentType.LOCAL_FOLDER_FILE, unique_id, search_space_id
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

        long_context_llm = await get_user_long_context_llm(
            session, user_id, search_space_id
        )

        title = full_path.name
        mtime = full_path.stat().st_mtime

        metadata_sections = [
            ("METADATA", [f"Title: {title}", f"Folder: {folder_name}", f"Path: {rel_path}"]),
            ("CONTENT", [content]),
        ]
        document_string = build_document_metadata_string(metadata_sections)

        summary_content = ""
        if long_context_llm and enable_summary:
            summary_content, _ = await generate_document_summary(
                document_string, long_context_llm, {"folder_name": folder_name, "file_path": rel_path}
            )

        embedding = embed_text(document_string)
        chunks = await create_document_chunks(document_string)

        doc_metadata = {
            "folder_name": folder_name,
            "file_path": rel_path,
            "summary": summary_content,
            "mtime": mtime,
        }

        if existing:
            existing.title = title
            existing.content = document_string
            existing.content_hash = content_hash
            existing.source_markdown = content
            existing.embedding = embedding
            existing.document_metadata = doc_metadata
            await safe_set_chunks(session, existing, chunks)
            existing.updated_at = get_current_timestamp()
            existing.status = DocumentStatus.ready()
        else:
            document = Document(
                search_space_id=search_space_id,
                title=title,
                document_type=DocumentType.LOCAL_FOLDER_FILE,
                document_metadata=doc_metadata,
                content=document_string,
                content_hash=content_hash,
                unique_identifier_hash=uid_hash,
                source_markdown=content,
                embedding=embedding,
                status=DocumentStatus.ready(),
                updated_at=get_current_timestamp(),
                created_by_id=user_id,
                connector_id=None,
            )
            session.add(document)
            await session.flush()
            for chunk in chunks:
                chunk.document_id = document.id
            session.add_all(chunks)

        await session.commit()

        await task_logger.log_task_success(
            log_entry,
            f"Single file indexed: {rel_path}",
            {"file": rel_path},
        )
        return 1, 0, None

    except Exception as e:
        logger.exception(f"Error indexing single file {target_file_path}: {e}")
        await session.rollback()
        return 0, 0, str(e)
