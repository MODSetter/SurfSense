"""
Service for charging the unified credit wallet for ETL document processing.

Replaces the legacy ``PageLimitService`` page-quota model. Page counts are
still estimated the same way; they are now converted to USD micro-credits
(``config.MICROS_PER_PAGE`` per page, times a per-mode multiplier) and debited
from ``user.credit_micros_balance``.

When ``config.ETL_CREDIT_BILLING_ENABLED`` is False (the default for
self-hosted / OSS installs) every check/charge is a no-op, preserving the prior
effectively-unlimited ETL behaviour.
"""

import os
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config


class InsufficientCreditsError(Exception):
    """Raised when a user lacks enough credit to process a document."""

    def __init__(
        self,
        message: str = "Insufficient credits to process this document. "
        "Add more credits to continue.",
        balance_micros: int = 0,
        required_micros: int = 0,
    ):
        self.balance_micros = balance_micros
        self.required_micros = required_micros
        super().__init__(message)


class EtlCreditService:
    """Checks and charges the credit wallet for ETL page processing."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def billing_enabled() -> bool:
        return config.ETL_CREDIT_BILLING_ENABLED

    @staticmethod
    def pages_to_micros(pages: int, multiplier: int = 1) -> int:
        """Convert a (multiplied) page count to USD micro-credits."""
        return int(pages) * int(multiplier) * config.MICROS_PER_PAGE

    async def get_available_micros(self, user_id: str) -> int | None:
        """Return spendable credit in micro-USD (``balance - reserved``).

        Returns ``None`` when ETL billing is disabled, which callers treat as
        "unlimited" (no batch skipping, no blocking).
        """
        if not config.ETL_CREDIT_BILLING_ENABLED:
            return None

        from app.db import User

        result = await self.session.execute(
            select(User.credit_micros_balance, User.credit_micros_reserved).where(
                User.id == user_id
            )
        )
        row = result.first()
        if not row:
            raise ValueError(f"User with ID {user_id} not found")

        balance, reserved = row
        return balance - reserved

    async def check_credits(
        self, user_id: str, estimated_pages: int = 1, multiplier: int = 1
    ) -> None:
        """Raise :class:`InsufficientCreditsError` if the user can't afford to
        process ``estimated_pages`` (times ``multiplier``).

        No-op when ETL billing is disabled.
        """
        if not config.ETL_CREDIT_BILLING_ENABLED:
            return

        required = self.pages_to_micros(estimated_pages, multiplier)
        available = await self.get_available_micros(user_id)
        if available is None:
            return

        if required > available:
            raise InsufficientCreditsError(
                message=(
                    "Processing this document would exceed your available "
                    f"credit. Available: ${available / 1_000_000:.2f}. "
                    f"This document costs about ${required / 1_000_000:.2f} "
                    f"({estimated_pages} page(s)). Add more credits to continue."
                ),
                balance_micros=available,
                required_micros=required,
            )

    async def charge_credits(
        self, user_id: str, pages: int, multiplier: int = 1
    ) -> int | None:
        """Debit the credit wallet after successful processing.

        The balance may dip slightly negative when the actual page count
        exceeds the pre-check estimate (the document is already processed),
        mirroring the prior ``allow_exceed=True`` semantics.

        Returns the new balance in micros, or ``None`` when billing is disabled.
        """
        if not config.ETL_CREDIT_BILLING_ENABLED:
            return None

        from app.db import User

        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.unique().scalar_one_or_none()
        if not user:
            raise ValueError(f"User with ID {user_id} not found")

        cost = self.pages_to_micros(pages, multiplier)
        user.credit_micros_balance -= cost
        await self.session.commit()
        await self.session.refresh(user)

        # Best-effort: fire an auto-reload check if the balance dropped low.
        try:
            from app.services.auto_reload_service import maybe_trigger_auto_reload

            await maybe_trigger_auto_reload(user_id)
        except Exception:
            pass

        return user.credit_micros_balance

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
