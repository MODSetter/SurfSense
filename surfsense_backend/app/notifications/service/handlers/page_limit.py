"""Notifications for exceeding the page limit."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.persistence import Notification
from app.notifications.service.base import BaseNotificationHandler

logger = logging.getLogger(__name__)


class PageLimitNotificationHandler(BaseNotificationHandler):
    """Notifications for exceeding the page limit."""

    def __init__(self):
        super().__init__("page_limit_exceeded")

    def _generate_operation_id(self, document_name: str, search_space_id: int) -> str:
        """Build a unique id for a page-limit notification."""
        import hashlib

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        # Create a short hash of document name to ensure uniqueness
        doc_hash = hashlib.md5(document_name.encode()).hexdigest()[:8]
        return f"page_limit_{search_space_id}_{timestamp}_{doc_hash}"

    async def notify_page_limit_exceeded(
        self,
        session: AsyncSession,
        user_id: UUID,
        document_name: str,
        document_type: str,
        search_space_id: int,
        pages_used: int,
        pages_limit: int,
        pages_to_add: int,
    ) -> Notification:
        """Notify that a document was blocked by the page limit."""
        operation_id = self._generate_operation_id(document_name, search_space_id)

        display_name = (
            document_name[:40] + "..." if len(document_name) > 40 else document_name
        )
        title = f"Page limit exceeded: {display_name}"
        message = f"This document has ~{pages_to_add} page(s) but you've used {pages_used}/{pages_limit} pages. Upgrade to process more documents."

        metadata = {
            "operation_id": operation_id,
            "document_name": document_name,
            "document_type": document_type,
            "pages_used": pages_used,
            "pages_limit": pages_limit,
            "pages_to_add": pages_to_add,
            "status": "failed",
            "error_type": "page_limit_exceeded",
            # Where the inbox item links to.
            "action_url": f"/dashboard/{search_space_id}/more-pages",
            "action_label": "Upgrade Plan",
        }

        notification = Notification(
            user_id=user_id,
            search_space_id=search_space_id,
            type=self.notification_type,
            title=title,
            message=message,
            notification_metadata=metadata,
        )
        session.add(notification)
        await session.commit()
        await session.refresh(notification)
        logger.info(
            f"Created page_limit_exceeded notification {notification.id} for user {user_id}"
        )
        return notification
