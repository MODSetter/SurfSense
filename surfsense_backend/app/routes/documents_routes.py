# Force asyncio to use standard event loop before unstructured imports

from typing import Annotated
import asyncio
import os
import string
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db import (
    Chunk,
    Document,
    DocumentType,
    SearchSpace,
    User,
    get_async_session,
)
from app.dependencies.limiter import limiter
from app.schemas import (
    DocumentRead,
    DocumentsCreate,
    DocumentUpdate,
    DocumentWithChunksRead,
    PaginatedResponse,
)
from app.users import current_active_user
from app.utils.check_ownership import check_ownership
from app.utils.verify_space_write_permission import verify_space_write_permission
from app.tasks.celery_tasks.document_tasks import (
    process_crawled_url_task,
    process_extension_document_task,
    process_file_upload_task,
    process_youtube_video_task,
)

try:
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
except RuntimeError as e:
    print("Error setting event loop policy", e)
    pass

os.environ["UNSTRUCTURED_HAS_PATCHED_LOOP"] = "1"


router = APIRouter()

# File upload security settings
MAX_FILE_SIZE_MB = 1024  # Maximum file size in MB (1GB)
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB chunks for streaming uploads

# Pagination limits
MAX_PAGE_SIZE = 1000  # Maximum documents per page (prevents memory exhaustion)
DEFAULT_PAGE_SIZE = 50  # Default page size when not specified

# Restricted allowlist of document file extensions
# SECURITY: Excludes executable script files (.py, .js, .java, etc.) to prevent code execution risks
ALLOWED_EXTENSIONS = {
    # Documents
    ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt",
    # Spreadsheets
    ".xls", ".xlsx", ".csv", ".ods",
    # Presentations
    ".ppt", ".pptx", ".odp",
    # Images (for OCR)
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp",
    # Audio files
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".wma", ".opus",
    # Videos (for media content)
    ".mp4", ".mov", ".avi", ".webm", ".mkv", ".flv", ".wmv",
    # Web/markup (non-executable)
    ".html", ".htm", ".xml", ".json", ".md", ".markdown", ".rst",
    # E-books
    ".epub", ".mobi",
    # Archives (for document collections)
    ".zip",
}

# Magic byte signatures for file type validation
# SECURITY: Validates actual file content, not just extension
MAGIC_SIGNATURES = {
    # Documents
    b"%PDF": [".pdf"],
    b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1": [".doc", ".xls", ".ppt"],  # OLE2 format
    b"PK\x03\x04": [".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp", ".epub", ".zip"],  # ZIP-based formats
    # Images
    b"\x89PNG\r\n\x1a\n": [".png"],
    b"\xff\xd8\xff": [".jpg", ".jpeg"],
    b"GIF87a": [".gif"],
    b"GIF89a": [".gif"],
    b"BM": [".bmp"],
    b"II*\x00": [".tiff"],  # Little-endian TIFF
    b"MM\x00*": [".tiff"],  # Big-endian TIFF
    # Audio formats
    b"ID3": [".mp3"],  # MP3 with ID3 tag
    b"\xff\xfb": [".mp3"],  # MP3 without ID3
    b"\xff\xf3": [".mp3"],  # MP3 MPEG-1 Layer 3
    b"\xff\xf2": [".mp3"],  # MP3 MPEG-2 Layer 3
    b"RIFF": [".wav", ".avi"],  # WAV and AVI use RIFF
    b"OggS": [".ogg", ".opus"],  # Ogg Vorbis/Opus
    b"fLaC": [".flac"],  # FLAC
    # Video formats handled by RIFF and MP4 check separately
    # Note: WebP uses RIFF but requires additional WEBP check at offset 8, handled separately
    # Text-based formats (no magic bytes, validated by extension only)
}

# Dangerous executable signatures to block (SECURITY)
# These indicate potentially malicious files that could be renamed to bypass validation
DANGEROUS_SIGNATURES = {
    b"MZ": "Windows executable (PE/EXE)",
    b"\x7fELF": "Linux/Unix executable (ELF)",
    b"\xca\xfe\xba\xbe": "Mach-O executable (macOS)",
    b"\xfe\xed\xfa\xce": "Mach-O 32-bit executable",
    b"\xfe\xed\xfa\xcf": "Mach-O 64-bit executable",
    b"\xcf\xfa\xed\xfe": "Mach-O reverse byte order",
    b"#!": "Shell script",
    b"\x50\x4b\x05\x06": "ZIP file with executable content",
}

# Extensions that are text-based and don't have magic bytes
TEXT_BASED_EXTENSIONS = {".txt", ".csv", ".html", ".htm", ".xml", ".json", ".md", ".markdown", ".rst", ".rtf"}

# Media extensions that may have variable magic bytes or complex validation
# These will skip strict magic byte validation but still check for known signatures if present
MEDIA_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".wma", ".opus", ".mp4", ".mov", ".avi", ".webm", ".mkv", ".flv", ".wmv"}

# MOBI file format constants
MOBI_SIGNATURE = b"BOOKMOBI"
MOBI_SIGNATURE_OFFSET = 60
MOBI_MIN_SIZE = MOBI_SIGNATURE_OFFSET + len(MOBI_SIGNATURE)  # 68 bytes

# WebP file format constants
WEBP_RIFF_SIGNATURE = b"RIFF"
WEBP_WEBP_SIGNATURE = b"WEBP"
WEBP_RIFF_SIZE = len(WEBP_RIFF_SIGNATURE)  # 4 bytes
WEBP_WEBP_OFFSET = 8
WEBP_MIN_SIZE = WEBP_WEBP_OFFSET + len(WEBP_WEBP_SIGNATURE)  # 12 bytes

# Error message template for file type spoofing
FILE_TYPE_SPOOFING_ERROR = "File content does not match extension '{}'. Possible file type spoofing detected."


def validate_magic_bytes(content: bytes, file_ext: str) -> tuple[bool, str]:
    """
    Validate file content against magic byte signatures.

    Returns:
        Tuple of (is_valid, error_message)
    """
    # SECURITY: First check for dangerous executable signatures
    # This prevents malicious executables renamed as media files
    for dangerous_sig, description in DANGEROUS_SIGNATURES.items():
        if content.startswith(dangerous_sig):
            return False, f"Rejected: File contains {description} signature. Possible malicious file disguised as {file_ext}."

    # Text-based files don't have reliable magic bytes
    if file_ext in TEXT_BASED_EXTENSIONS:
        return True, ""

    # MOBI files have "BOOKMOBI" signature at offset 60
    if file_ext == ".mobi":
        if len(content) >= MOBI_MIN_SIZE and content[MOBI_SIGNATURE_OFFSET:MOBI_MIN_SIZE] == MOBI_SIGNATURE:
            return True, ""
        return False, FILE_TYPE_SPOOFING_ERROR.format(file_ext)

    # WebP files start with RIFF but need "WEBP" at offset 8
    if file_ext == ".webp":
        if (
            len(content) >= WEBP_MIN_SIZE
            and content[:WEBP_RIFF_SIZE] == WEBP_RIFF_SIGNATURE
            and content[WEBP_WEBP_OFFSET:WEBP_MIN_SIZE] == WEBP_WEBP_SIGNATURE
        ):
            return True, ""
        return False, FILE_TYPE_SPOOFING_ERROR.format(file_ext)

    # Special handling for MP4/M4A/MOV files (ftyp at offset 4)
    if file_ext in [".mp4", ".m4a", ".mov"] and len(content) >= 12:
        if content[4:8] == b"ftyp":
            return True, ""

    # Check against known magic signatures
    for magic, valid_extensions in MAGIC_SIGNATURES.items():
        if content.startswith(magic):
            if file_ext in valid_extensions:
                return True, ""
            else:
                # File content doesn't match claimed extension
                return False, FILE_TYPE_SPOOFING_ERROR.format(file_ext)

    # Media files (audio/video) can have complex or variable formats
    # Allow them through if no signature matched AND no dangerous signature detected
    # The dangerous signature check above prevents executables from passing through
    if file_ext in MEDIA_EXTENSIONS:
        return True, ""

    # No matching signature found for non-text, non-media file
    return False, f"Unable to verify file type for extension '{file_ext}'. File may be corrupted or spoofed."


def normalize_page_size(page_size: int) -> int:
    """
    Normalize page_size parameter to safe limits.

    Args:
        page_size: Requested page size (-1 for all, or positive integer)

    Returns:
        Normalized page size between 1 and MAX_PAGE_SIZE

    Example:
        >>> normalize_page_size(-1)
        1000  # MAX_PAGE_SIZE
        >>> normalize_page_size(5000)
        1000  # MAX_PAGE_SIZE
        >>> normalize_page_size(25)
        25
        >>> normalize_page_size(0)
        50  # DEFAULT_PAGE_SIZE
    """
    if page_size == -1 or page_size > MAX_PAGE_SIZE:
        return MAX_PAGE_SIZE
    elif page_size < 1:
        return DEFAULT_PAGE_SIZE
    return page_size


def validate_document_types(document_types: str | None) -> list[str]:
    """
    Validate and parse document types parameter.

    Args:
        document_types: Comma-separated string of document types

    Returns:
        List of valid DocumentType enum values

    Raises:
        HTTPException: If invalid types are provided

    Example:
        >>> validate_document_types("FILE,CRAWLED_URL")
        ['FILE', 'CRAWLED_URL']
        >>> validate_document_types("INVALID")
        HTTPException(400, "Invalid document types: INVALID. Valid types: ...")
    """
    if not document_types or not document_types.strip():
        return []

    # Get valid enum values
    valid_types = {e.value for e in DocumentType}

    # Parse and validate
    type_list = [t.strip() for t in document_types.split(",") if t.strip()]
    invalid_types = [t for t in type_list if t not in valid_types]

    if invalid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document types: {', '.join(invalid_types)}. "
            f"Valid types: {', '.join(sorted(valid_types))}",
        )

    return type_list


def sanitize_file_extension(filename: str) -> str:
    """
    Sanitize file extension to prevent path traversal attacks.

    Extracts the file extension and removes any dangerous characters
    that could be used for directory traversal or other attacks.

    Args:
        filename: Original filename from upload

    Returns:
        Sanitized file extension (e.g., ".pdf", ".txt")
        Returns ".bin" if extension is invalid or suspicious

    Security:
        - Strips all characters except alphanumeric and dot
        - Prevents path traversal attempts like "../../etc/passwd%00.pdf"
        - Prevents null byte injection
        - Returns safe default for suspicious extensions

    Example:
        >>> sanitize_file_extension("../../etc/passwd%00.pdf")
        '.pdf'
        >>> sanitize_file_extension("document.pdf")
        '.pdf'
        >>> sanitize_file_extension("file")
        '.bin'
    """
    # Extract extension and convert to lowercase
    raw_file_ext = os.path.splitext(filename)[1].lower()

    # Only allow safe characters: alphanumeric and dot
    allowed_chars = string.ascii_lowercase + string.digits + "."
    file_ext = "".join(c for c in raw_file_ext if c in allowed_chars)

    # Validate the sanitized extension
    if not file_ext or file_ext == "." or file_ext not in ALLOWED_EXTENSIONS:
        # Default to .bin for invalid or suspicious extensions
        return ".bin"

    return file_ext


def validate_file_upload(file: UploadFile) -> tuple[bool, str]:
    """
    Validate a file upload for security.

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check filename exists
    if not file.filename:
        return False, "File must have a filename"

    # Sanitize and check file extension (prevents path traversal)
    file_ext = sanitize_file_extension(file.filename)
    if file_ext == ".bin":
        # Suspicious or invalid extension was sanitized to .bin
        raw_ext = os.path.splitext(file.filename)[1]
        return False, f"File extension '{raw_ext}' is invalid or not allowed. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
    if file_ext not in ALLOWED_EXTENSIONS:
        return False, f"File type '{file_ext}' is not allowed. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"

    # Check content type if available (basic MIME validation)
    if file.content_type:
        # Block potentially dangerous content types
        dangerous_types = [
            "application/x-executable",
            "application/x-msdownload",
            "application/x-msdos-program",
        ]
        if file.content_type in dangerous_types:
            return False, f"Content type '{file.content_type}' is not allowed"

    return True, ""


@router.post("/documents")
@limiter.limit("20/minute")  # Limit document creation to prevent spam
async def create_documents(
    request: Request,
    data: DocumentsCreate = Body(...),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        # CRITICAL SECURITY: Verify user has write permission (public spaces are read-only for non-owners)
        await verify_space_write_permission(session, data.search_space_id, user)

        if data.document_type == DocumentType.EXTENSION:
            for individual_document in data.content:
                # Convert document to dict for Celery serialization
                document_dict = {
                    "metadata": {
                        "VisitedWebPageTitle": individual_document.metadata.VisitedWebPageTitle,
                        "VisitedWebPageURL": individual_document.metadata.VisitedWebPageURL,
                    },
                    "content": individual_document.content,
                }
                process_extension_document_task.delay(
                    document_dict, data.search_space_id, str(user.id)
                )
        elif data.document_type == DocumentType.CRAWLED_URL:
            for url in data.content:
                process_crawled_url_task.delay(
                    url, data.search_space_id, str(user.id)
                )
        elif data.document_type == DocumentType.YOUTUBE_VIDEO:

            for url in data.content:
                process_youtube_video_task.delay(
                    url, data.search_space_id, str(user.id)
                )
        else:
            raise HTTPException(status_code=400, detail="Invalid document type")

        await session.commit()
        return {"message": "Documents processed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to process documents: {e!s}"
        ) from e


@router.post("/documents/fileupload")
@limiter.limit("10/minute")  # 10 uploads per minute per IP
async def create_documents_file_upload(
    request: Request,
    files: list[UploadFile] = File(...),
    search_space_id: int = Form(...),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        # CRITICAL SECURITY: Verify user has write permission (public spaces are read-only for non-owners)
        await verify_space_write_permission(session, search_space_id, user)

        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        # Validate all files first before processing any
        for file in files:
            is_valid, error_msg = validate_file_upload(file)
            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file '{file.filename}': {error_msg}",
                )

        for file in files:
            temp_path = None
            try:
                # Validate file size from headers before reading (prevent DoS)
                if file.size and file.size > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File '{file.filename}' exceeds maximum size of {MAX_FILE_SIZE_MB}MB",
                    )

                # Sanitize file extension to prevent path traversal attacks
                file_ext = sanitize_file_extension(file.filename)

                # Create uploads directory if it doesn't exist
                uploads_dir = Path(os.getenv("UPLOADS_DIR", "./uploads"))
                uploads_dir.mkdir(parents=True, exist_ok=True)
                unique_filename = f"{uuid.uuid4()}{file_ext}"
                temp_path = uploads_dir / unique_filename

                # Stream file to disk in chunks (constant memory usage)
                total_bytes = 0
                first_chunk = None

                async with aiofiles.open(temp_path, 'wb') as f:
                    while chunk := await file.read(CHUNK_SIZE):
                        # Store first chunk for magic byte validation
                        if first_chunk is None:
                            first_chunk = chunk

                        await f.write(chunk)
                        total_bytes += len(chunk)

                        # Safety check during streaming (prevent size limit bypass)
                        if total_bytes > MAX_FILE_SIZE_BYTES:
                            raise HTTPException(
                                status_code=400,
                                detail=f"File '{file.filename}' exceeds maximum size of {MAX_FILE_SIZE_MB}MB",
                            )

                # Validate magic bytes using first chunk (skip for empty files)
                if first_chunk:
                    is_valid, error_msg = validate_magic_bytes(first_chunk, file_ext)
                    if not is_valid:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Invalid file '{file.filename}': {error_msg}",
                        )

                # File successfully streamed to disk, queue for processing
                process_file_upload_task.delay(
                    str(temp_path), file.filename, search_space_id, str(user.id)
                )

            except HTTPException:
                # Clean up temp file on validation errors
                if temp_path and temp_path.exists():
                    temp_path.unlink()
                raise
            except Exception as e:
                # Clean up temp file on unexpected errors
                if temp_path and temp_path.exists():
                    temp_path.unlink()
                raise HTTPException(
                    status_code=422,
                    detail=f"Failed to process file {file.filename}: {e!s}",
                ) from e

        await session.commit()
        return {"message": "Files uploaded for processing"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to upload files: {e!s}"
        ) from e


@router.get("/documents", response_model=PaginatedResponse[DocumentRead])
async def read_documents(
    skip: int | None = None,
    page: int | None = None,
    page_size: int = 50,
    search_space_id: int | None = None,
    document_types: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List documents owned by the current user, with optional filtering and pagination.

    Args:
        skip: Absolute number of items to skip from the beginning. If provided, it takes precedence over 'page'.
        page: Zero-based page index used when 'skip' is not provided.
        page_size: Number of items per page (default: 50). Use -1 to return all remaining items after the offset.
        search_space_id: If provided, restrict results to a specific search space.
        document_types: Comma-separated list of document types to filter by (e.g., "EXTENSION,FILE,SLACK_CONNECTOR").
        session: Database session (injected).
        user: Current authenticated user (injected).

    Returns:
        PaginatedResponse[DocumentRead]: Paginated list of documents visible to the user.

    Notes:
        - If both 'skip' and 'page' are provided, 'skip' is used.
        - Results are scoped to documents owned by the current user.
    """
    try:
        from sqlalchemy import func

        # Normalize page_size to prevent memory exhaustion
        page_size = normalize_page_size(page_size)

        query = (
            select(Document).join(SearchSpace).filter(SearchSpace.user_id == user.id)
        )

        # Filter by search_space_id if provided
        if search_space_id is not None:
            query = query.filter(Document.search_space_id == search_space_id)

        # Validate and filter by document_types if provided
        type_list = validate_document_types(document_types)
        if type_list:
            query = query.filter(Document.document_type.in_(type_list))

        # Get total count
        count_query = (
            select(func.count())
            .select_from(Document)
            .join(SearchSpace)
            .filter(SearchSpace.user_id == user.id)
        )
        if search_space_id is not None:
            count_query = count_query.filter(
                Document.search_space_id == search_space_id
            )
        if type_list:
            count_query = count_query.filter(Document.document_type.in_(type_list))
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        # Calculate offset
        offset = 0
        if skip is not None:
            offset = skip
        elif page is not None:
            offset = page * page_size

        # Get paginated results (page_size is already normalized to MAX_PAGE_SIZE)
        result = await session.execute(query.offset(offset).limit(page_size))

        db_documents = result.scalars().all()

        # Convert database objects to API-friendly format
        api_documents = []
        for doc in db_documents:
            api_documents.append(
                DocumentRead(
                    id=doc.id,
                    title=doc.title,
                    document_type=doc.document_type,
                    document_metadata=doc.document_metadata,
                    content=doc.content,
                    created_at=doc.created_at,
                    search_space_id=doc.search_space_id,
                )
            )

        return PaginatedResponse(items=api_documents, total=total)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch documents: {e!s}"
        ) from e


@router.get("/documents/search", response_model=PaginatedResponse[DocumentRead])
async def search_documents(
    title: str,
    skip: int | None = None,
    page: int | None = None,
    page_size: int = 50,
    search_space_id: int | None = None,
    document_types: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Search documents by title substring, optionally filtered by search_space_id and document_types.

    Args:
        title: Case-insensitive substring to match against document titles. Required.
        skip: Absolute number of items to skip from the beginning. If provided, it takes precedence over 'page'. Default: None.
        page: Zero-based page index used when 'skip' is not provided. Default: None.
        page_size: Number of items per page. Use -1 to return all remaining items after the offset. Default: 50.
        search_space_id: Filter results to a specific search space. Default: None.
        document_types: Comma-separated list of document types to filter by (e.g., "EXTENSION,FILE,SLACK_CONNECTOR").
        session: Database session (injected).
        user: Current authenticated user (injected).

    Returns:
        PaginatedResponse[DocumentRead]: Paginated list of documents matching the query and filter.

    Notes:
        - Title matching uses ILIKE (case-insensitive).
        - If both 'skip' and 'page' are provided, 'skip' is used.
    """
    try:
        from sqlalchemy import func

        # Normalize page_size to prevent memory exhaustion
        page_size = normalize_page_size(page_size)

        query = (
            select(Document).join(SearchSpace).filter(SearchSpace.user_id == user.id)
        )
        if search_space_id is not None:
            query = query.filter(Document.search_space_id == search_space_id)

        # Only search by title (case-insensitive)
        query = query.filter(Document.title.ilike(f"%{title}%"))

        # Validate and filter by document_types if provided
        type_list = validate_document_types(document_types)
        if type_list:
            query = query.filter(Document.document_type.in_(type_list))

        # Get total count
        count_query = (
            select(func.count())
            .select_from(Document)
            .join(SearchSpace)
            .filter(SearchSpace.user_id == user.id)
        )
        if search_space_id is not None:
            count_query = count_query.filter(
                Document.search_space_id == search_space_id
            )
        count_query = count_query.filter(Document.title.ilike(f"%{title}%"))
        if type_list:
            count_query = count_query.filter(Document.document_type.in_(type_list))
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        # Calculate offset
        offset = 0
        if skip is not None:
            offset = skip
        elif page is not None:
            offset = page * page_size

        # Get paginated results (page_size is already normalized to MAX_PAGE_SIZE)
        result = await session.execute(query.offset(offset).limit(page_size))

        db_documents = result.scalars().all()

        # Convert database objects to API-friendly format
        api_documents = []
        for doc in db_documents:
            api_documents.append(
                DocumentRead(
                    id=doc.id,
                    title=doc.title,
                    document_type=doc.document_type,
                    document_metadata=doc.document_metadata,
                    content=doc.content,
                    created_at=doc.created_at,
                    search_space_id=doc.search_space_id,
                )
            )

        return PaginatedResponse(items=api_documents, total=total)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to search documents: {e!s}"
        ) from e


@router.get("/documents/type-counts")
async def get_document_type_counts(
    search_space_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get counts of documents by type for the current user.

    Args:
        search_space_id: If provided, restrict counts to a specific search space.
        session: Database session (injected).
        user: Current authenticated user (injected).

    Returns:
        Dict mapping document types to their counts.
    """
    try:
        from sqlalchemy import func

        query = (
            select(Document.document_type, func.count(Document.id))
            .join(SearchSpace)
            .filter(SearchSpace.user_id == user.id)
            .group_by(Document.document_type)
        )

        if search_space_id is not None:
            query = query.filter(Document.search_space_id == search_space_id)

        result = await session.execute(query)
        type_counts = dict(result.all())

        return type_counts
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch document type counts: {e!s}"
        ) from e


@router.get("/documents/by-chunk/{chunk_id}", response_model=DocumentWithChunksRead)
async def get_document_by_chunk_id(
    chunk_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Retrieves a document based on a chunk ID, including all its chunks ordered by creation time.
    The document's embedding and chunk embeddings are excluded from the response.
    """
    try:
        # First, get the chunk and verify it exists
        chunk_result = await session.execute(select(Chunk).filter(Chunk.id == chunk_id))
        chunk = chunk_result.scalars().first()

        if not chunk:
            raise HTTPException(
                status_code=404, detail=f"Chunk with id {chunk_id} not found"
            )

        # Get the associated document and verify ownership
        document_result = await session.execute(
            select(Document)
            .options(selectinload(Document.chunks))
            .join(SearchSpace)
            .filter(Document.id == chunk.document_id, SearchSpace.user_id == user.id)
        )
        document = document_result.scalars().first()

        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found or you don't have access to it",
            )

        # Sort chunks by creation time
        sorted_chunks = sorted(document.chunks, key=lambda x: x.created_at)

        # Return the document with its chunks
        return DocumentWithChunksRead(
            id=document.id,
            title=document.title,
            document_type=document.document_type,
            document_metadata=document.document_metadata,
            content=document.content,
            created_at=document.created_at,
            search_space_id=document.search_space_id,
            chunks=sorted_chunks,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve document: {e!s}"
        ) from e


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def read_document(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        result = await session.execute(
            select(Document)
            .join(SearchSpace)
            .filter(Document.id == document_id, SearchSpace.user_id == user.id)
        )
        document = result.scalars().first()

        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document with id {document_id} not found"
            )

        # Convert database object to API-friendly format
        return DocumentRead(
            id=document.id,
            title=document.title,
            document_type=document.document_type,
            document_metadata=document.document_metadata,
            content=document.content,
            created_at=document.created_at,
            search_space_id=document.search_space_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch document: {e!s}"
        ) from e


@router.put("/documents/{document_id}", response_model=DocumentRead)
@limiter.limit("30/minute")  # Limit document updates
async def update_document(
    request: Request,
    document_id: int,
    document_update: DocumentUpdate = Body(...),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        # Query the document directly instead of using read_document function
        result = await session.execute(
            select(Document)
            .join(SearchSpace)
            .filter(Document.id == document_id, SearchSpace.user_id == user.id)
        )
        db_document = result.scalars().first()

        if not db_document:
            raise HTTPException(
                status_code=404, detail=f"Document with id {document_id} not found"
            )

        update_data = document_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_document, key, value)
        await session.commit()
        await session.refresh(db_document)

        # Convert to DocumentRead for response
        return DocumentRead(
            id=db_document.id,
            title=db_document.title,
            document_type=db_document.document_type,
            document_metadata=db_document.document_metadata,
            content=db_document.content,
            created_at=db_document.created_at,
            search_space_id=db_document.search_space_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update document: {e!s}"
        ) from e


@router.delete("/documents/{document_id}", response_model=dict)
@limiter.limit("20/minute")  # Limit document deletion to prevent abuse
async def delete_document(
    request: Request,
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        # Query the document directly instead of using read_document function
        result = await session.execute(
            select(Document)
            .join(SearchSpace)
            .filter(Document.id == document_id, SearchSpace.user_id == user.id)
        )
        document = result.scalars().first()

        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document with id {document_id} not found"
            )

        await session.delete(document)
        await session.commit()
        return {"message": "Document deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete document: {e!s}"
        ) from e
