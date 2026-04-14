"""
Service for managing user page limits for ETL services.
"""

import os
from pathlib import Path, PurePosixPath

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

        # Get user's current page usage and subscription status
        result = await self.session.execute(
            select(User.pages_used, User.pages_limit, User.subscription_status).where(
                User.id == user_id
            )
        )
        row = result.first()

        if not row:
            raise ValueError(f"User with ID {user_id} not found")

        pages_used, pages_limit, sub_status = row

        # PAST_DUE: enforce free-tier page limit to prevent usage without payment
        if str(sub_status).lower() == "past_due":
            from app.config import config as app_config  # avoid circular import

            free_limit = app_config.PLAN_LIMITS.get("free", {}).get("pages_limit", 500)
            pages_limit = min(pages_limit, free_limit)

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

    @staticmethod
    def estimate_pages_from_metadata(
        file_name_or_ext: str, file_size: int | str | None = None
    ) -> int:
        """Size-based page estimation from file name/extension and byte size.

        Pure function — no file I/O, no database access.  Used by cloud
        connectors (which only have API metadata) and as the internal
        fallback for :meth:`estimate_pages_before_processing`.

        ``file_name_or_ext`` can be a full filename (``"report.pdf"``) or
        a bare extension (``".pdf"``).  ``file_size`` may be an int, a
        stringified int from a cloud API, or *None*.
        """
        if file_size is not None:
            try:
                file_size = int(file_size)
            except (ValueError, TypeError):
                file_size = 0
        else:
            file_size = 0

        if file_size <= 0:
            return 1

        ext = PurePosixPath(file_name_or_ext).suffix.lower() if file_name_or_ext else ""
        if not ext and file_name_or_ext.startswith("."):
            ext = file_name_or_ext.lower()
        file_ext = ext

        if file_ext == ".pdf":
            return max(1, file_size // (100 * 1024))

        if file_ext in {
            ".doc",
            ".docx",
            ".docm",
            ".dot",
            ".dotm",
            ".odt",
            ".ott",
            ".sxw",
            ".stw",
            ".uot",
            ".rtf",
            ".pages",
            ".wpd",
            ".wps",
            ".abw",
            ".zabw",
            ".cwk",
            ".hwp",
            ".lwp",
            ".mcw",
            ".mw",
            ".sdw",
            ".vor",
        }:
            return max(1, file_size // (50 * 1024))

        if file_ext in {
            ".ppt",
            ".pptx",
            ".pptm",
            ".pot",
            ".potx",
            ".odp",
            ".otp",
            ".sxi",
            ".sti",
            ".uop",
            ".key",
            ".sda",
            ".sdd",
            ".sdp",
        }:
            return max(1, file_size // (200 * 1024))

        if file_ext in {
            ".xls",
            ".xlsx",
            ".xlsm",
            ".xlsb",
            ".xlw",
            ".xlr",
            ".ods",
            ".ots",
            ".fods",
            ".numbers",
            ".123",
            ".wk1",
            ".wk2",
            ".wk3",
            ".wk4",
            ".wks",
            ".wb1",
            ".wb2",
            ".wb3",
            ".wq1",
            ".wq2",
            ".csv",
            ".tsv",
            ".slk",
            ".sylk",
            ".dif",
            ".dbf",
            ".prn",
            ".qpw",
            ".602",
            ".et",
            ".eth",
        }:
            return max(1, file_size // (100 * 1024))

        if file_ext in {".epub"}:
            return max(1, file_size // (50 * 1024))

        if file_ext in {".txt", ".log", ".md", ".markdown", ".htm", ".html", ".xml"}:
            return max(1, file_size // 3000)

        if file_ext in {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".tiff",
            ".webp",
            ".svg",
            ".cgm",
            ".odg",
            ".pbd",
        }:
            return 1

        if file_ext in {".mp3", ".m4a", ".wav", ".mpga"}:
            return max(1, file_size // (1024 * 1024))

        if file_ext in {".mp4", ".mpeg", ".webm"}:
            return max(1, file_size // (5 * 1024 * 1024))

        return max(1, file_size // (80 * 1024))

    def estimate_pages_before_processing(self, file_path: str) -> int:
        """
        Estimate page count from a local file before processing.

        For PDFs, attempts to read the actual page count via pypdf.
        For everything else, delegates to :meth:`estimate_pages_from_metadata`.

        Args:
            file_path: Path to the file

        Returns:
            Estimated number of pages
        """
        if not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")

        file_ext = Path(file_path).suffix.lower()
        file_size = os.path.getsize(file_path)

        if file_ext == ".pdf":
            try:
                import pypdf

                with open(file_path, "rb") as f:
                    pdf_reader = pypdf.PdfReader(f)
                    return len(pdf_reader.pages)
            except Exception:
                pass  # fall through to size-based estimation

        return self.estimate_pages_from_metadata(file_ext, file_size)
