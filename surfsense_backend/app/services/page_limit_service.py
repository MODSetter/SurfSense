"""
Service for managing user page limits for ETL services.
"""

import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class PageLimitExceededError(Exception):
    """
    Exception raised when a user exceeds their page processing limit.
    """

    def __init__(
        self,
        message: str = "Page limit exceeded. Please contact admin to increase limits for your account.",
        pages_used: int = 0,
        pages_limit: int = 0,
        pages_to_add: int = 0,
    ):
        self.pages_used = pages_used
        self.pages_limit = pages_limit
        self.pages_to_add = pages_to_add
        super().__init__(message)


class PageLimitService:
    """Service for checking and updating user page limits."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def check_page_limit(
        self, user_id: str, estimated_pages: int = 1
    ) -> tuple[bool, int, int]:
        """
        Check if user has enough pages remaining for processing.

        Args:
            user_id: The user's ID
            estimated_pages: Estimated number of pages to be processed

        Returns:
            Tuple of (has_capacity, pages_used, pages_limit)

        Raises:
            PageLimitExceededError: If user would exceed their page limit
        """
        from app.db import User

        # Get user's current page usage
        result = await self.session.execute(
            select(User.pages_used, User.pages_limit).where(User.id == user_id)
        )
        row = result.first()

        if not row:
            raise ValueError(f"User with ID {user_id} not found")

        pages_used, pages_limit = row

        # Check if adding estimated pages would exceed limit
        if pages_used + estimated_pages > pages_limit:
            raise PageLimitExceededError(
                message=f"Processing this document would exceed your page limit. "
                f"Used: {pages_used}/{pages_limit} pages. "
                f"Document has approximately {estimated_pages} page(s). "
                f"Please contact admin to increase limits for your account.",
                pages_used=pages_used,
                pages_limit=pages_limit,
                pages_to_add=estimated_pages,
            )

        return True, pages_used, pages_limit

    async def update_page_usage(
        self, user_id: str, pages_to_add: int, allow_exceed: bool = False
    ) -> int:
        """
        Update user's page usage after successful processing.

        Args:
            user_id: The user's ID
            pages_to_add: Number of pages to add to usage
            allow_exceed: If True, allows update even if it exceeds limit
                         (used when document was already processed after passing initial check)

        Returns:
            New total pages_used value

        Raises:
            PageLimitExceededError: If adding pages would exceed limit and allow_exceed is False
        """
        from app.db import User

        # Get user
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.unique().scalar_one_or_none()

        if not user:
            raise ValueError(f"User with ID {user_id} not found")

        # Check if this would exceed limit (only if allow_exceed is False)
        new_usage = user.pages_used + pages_to_add
        if not allow_exceed and new_usage > user.pages_limit:
            raise PageLimitExceededError(
                message=f"Cannot update page usage. Would exceed limit. "
                f"Current: {user.pages_used}/{user.pages_limit}, "
                f"Trying to add: {pages_to_add}",
                pages_used=user.pages_used,
                pages_limit=user.pages_limit,
                pages_to_add=pages_to_add,
            )

        # Update usage
        user.pages_used = new_usage
        await self.session.commit()
        await self.session.refresh(user)

        return user.pages_used

    async def get_page_usage(self, user_id: str) -> tuple[int, int]:
        """
        Get user's current page usage and limit.

        Args:
            user_id: The user's ID

        Returns:
            Tuple of (pages_used, pages_limit)
        """
        from app.db import User

        result = await self.session.execute(
            select(User.pages_used, User.pages_limit).where(User.id == user_id)
        )
        row = result.first()

        if not row:
            raise ValueError(f"User with ID {user_id} not found")

        return row

    def estimate_pages_from_elements(self, elements: list) -> int:
        """
        Estimate page count from document elements (for Unstructured).

        Args:
            elements: List of document elements

        Returns:
            Estimated number of pages
        """
        # For Unstructured, we can count unique page numbers in metadata
        # or estimate based on content length
        page_numbers = set()

        for element in elements:
            # Try to get page number from metadata
            if hasattr(element, "metadata") and element.metadata:
                page_num = element.metadata.get("page_number")
                if page_num is not None:
                    page_numbers.add(page_num)

        # If we found page numbers in metadata, use that count
        if page_numbers:
            return len(page_numbers)

        # Otherwise, estimate: assume ~2000 chars per page
        total_content_length = sum(
            len(element.page_content) if hasattr(element, "page_content") else 0
            for element in elements
        )
        estimated_pages = max(1, total_content_length // 2000)

        return estimated_pages

    def estimate_pages_from_markdown(self, markdown_documents: list) -> int:
        """
        Estimate page count from markdown documents (for LlamaCloud).

        Args:
            markdown_documents: List of markdown document objects

        Returns:
            Estimated number of pages
        """
        # For LlamaCloud, if split_by_page=True was used, each doc is a page
        # Otherwise, estimate based on content length
        if not markdown_documents:
            return 1

        # Check if documents have page metadata
        total_pages = 0
        for doc in markdown_documents:
            if hasattr(doc, "metadata") and doc.metadata:
                # If metadata contains page info, use it
                page_num = doc.metadata.get("page", doc.metadata.get("page_number"))
                if page_num is not None:
                    total_pages += 1
                    continue

            # Otherwise estimate from content length
            content_length = len(doc.text) if hasattr(doc, "text") else 0
            estimated = max(1, content_length // 2000)
            total_pages += estimated

        return max(1, total_pages)

    def estimate_pages_from_content_length(self, content_length: int) -> int:
        """
        Estimate page count from content length (for Docling).

        Args:
            content_length: Length of the document content

        Returns:
            Estimated number of pages
        """
        # Estimate ~2000 characters per page
        return max(1, content_length // 2000)

    def estimate_pages_before_processing(self, file_path: str) -> int:
        """
        Estimate page count from file before processing (to avoid unnecessary API calls).
        This is called BEFORE sending to ETL services to prevent cost on rejected files.

        Args:
            file_path: Path to the file

        Returns:
            Estimated number of pages
        """
        if not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")

        file_ext = Path(file_path).suffix.lower()
        file_size = os.path.getsize(file_path)

        # PDF files - try to get actual page count
        if file_ext == ".pdf":
            try:
                import pypdf

                with open(file_path, "rb") as f:
                    pdf_reader = pypdf.PdfReader(f)
                    return len(pdf_reader.pages)
            except Exception:
                # If PDF reading fails, fall back to size estimation
                # Typical PDF: ~100KB per page (conservative estimate)
                return max(1, file_size // (100 * 1024))

        # Word Processing Documents
        # Microsoft Word, LibreOffice Writer, WordPerfect, Pages, etc.
        elif file_ext in [
            ".doc",
            ".docx",
            ".docm",
            ".dot",
            ".dotm",  # Microsoft Word
            ".odt",
            ".ott",
            ".sxw",
            ".stw",
            ".uot",  # OpenDocument/StarOffice Writer
            ".rtf",  # Rich Text Format
            ".pages",  # Apple Pages
            ".wpd",
            ".wps",  # WordPerfect, Microsoft Works
            ".abw",
            ".zabw",  # AbiWord
            ".cwk",
            ".hwp",
            ".lwp",
            ".mcw",
            ".mw",
            ".sdw",
            ".vor",  # Other word processors
        ]:
            # Typical word document: ~50KB per page (conservative)
            return max(1, file_size // (50 * 1024))

        # Presentation Documents
        # PowerPoint, Impress, Keynote, etc.
        elif file_ext in [
            ".ppt",
            ".pptx",
            ".pptm",
            ".pot",
            ".potx",  # Microsoft PowerPoint
            ".odp",
            ".otp",
            ".sxi",
            ".sti",
            ".uop",  # OpenDocument/StarOffice Impress
            ".key",  # Apple Keynote
            ".sda",
            ".sdd",
            ".sdp",  # StarOffice Draw/Impress
        ]:
            # Typical presentation: ~200KB per slide (conservative)
            return max(1, file_size // (200 * 1024))

        # Spreadsheet Documents
        # Excel, Calc, Numbers, Lotus, etc.
        elif file_ext in [
            ".xls",
            ".xlsx",
            ".xlsm",
            ".xlsb",
            ".xlw",
            ".xlr",  # Microsoft Excel
            ".ods",
            ".ots",
            ".fods",  # OpenDocument Spreadsheet
            ".numbers",  # Apple Numbers
            ".123",
            ".wk1",
            ".wk2",
            ".wk3",
            ".wk4",
            ".wks",  # Lotus 1-2-3
            ".wb1",
            ".wb2",
            ".wb3",
            ".wq1",
            ".wq2",  # Quattro Pro
            ".csv",
            ".tsv",
            ".slk",
            ".sylk",
            ".dif",
            ".dbf",
            ".prn",
            ".qpw",  # Data formats
            ".602",
            ".et",
            ".eth",  # Other spreadsheets
        ]:
            # Spreadsheets typically have 1 sheet = 1 page for ETL
            # Conservative: ~100KB per sheet
            return max(1, file_size // (100 * 1024))

        # E-books
        elif file_ext in [".epub"]:
            # E-books vary widely, estimate by size
            # Typical e-book: ~50KB per page
            return max(1, file_size // (50 * 1024))

        # Plain Text and Markup Files
        elif file_ext in [
            ".txt",
            ".log",  # Plain text
            ".md",
            ".markdown",  # Markdown
            ".htm",
            ".html",
            ".xml",  # Markup
        ]:
            # Plain text: ~3000 bytes per page
            return max(1, file_size // 3000)

        # Image Files
        # Each image is typically processed as 1 page
        elif file_ext in [
            ".jpg",
            ".jpeg",  # JPEG
            ".png",  # PNG
            ".gif",  # GIF
            ".bmp",  # Bitmap
            ".tiff",  # TIFF
            ".webp",  # WebP
            ".svg",  # SVG
            ".cgm",  # Computer Graphics Metafile
            ".odg",
            ".pbd",  # OpenDocument Graphics
        ]:
            # Each image = 1 page
            return 1

        # Audio Files (transcription = typically 1 page per minute)
        # Note: These should be handled by audio transcription flow, not ETL
        elif file_ext in [".mp3", ".m4a", ".wav", ".mpga"]:
            # Audio files: estimate based on duration
            # Fallback: ~1MB per minute of audio, 1 page per minute transcript
            return max(1, file_size // (1024 * 1024))

        # Video Files (typically not processed for pages, but just in case)
        elif file_ext in [".mp4", ".mpeg", ".webm"]:
            # Video files: very rough estimate
            # Typically wouldn't be page-based, but use conservative estimate
            return max(1, file_size // (5 * 1024 * 1024))

        # Other/Unknown Document Types
        else:
            # Conservative estimate: ~80KB per page
            # This catches: .sgl, .sxg, .uof, .uos1, .uos2, .web, and any future formats
            return max(1, file_size // (80 * 1024))
