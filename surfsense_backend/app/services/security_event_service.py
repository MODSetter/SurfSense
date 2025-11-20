"""
Security Event Logging Service.

Provides centralized logging for security-related events like 2FA actions,
login attempts, and other security-critical operations.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SecurityEvent, SecurityEventType

logger = logging.getLogger(__name__)


class SecurityEventService:
    """Service for logging security events to the database."""

    @staticmethod
    async def log_event(
        session: AsyncSession,
        event_type: SecurityEventType,
        user_id: UUID | str,
        success: bool = True,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> SecurityEvent | None:
        """
        Log a security event to the database.

        Args:
            session: Database session
            event_type: Type of security event
            user_id: ID of the user involved in the event
            success: Whether the event was successful (default: True)
            ip_address: IP address of the request (optional)
            user_agent: User agent string (optional)
            details: Additional details about the event (optional)

        Returns:
            The created SecurityEvent object, or None if logging failed
        """
        try:
            # Convert string user_id to UUID if needed
            if isinstance(user_id, str):
                user_id = UUID(user_id)

            event = SecurityEvent(
                event_type=event_type,
                user_id=user_id,
                success=success,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details or {},
            )

            session.add(event)
            await session.commit()
            await session.refresh(event)

            logger.info(
                f"Security event logged: {event_type.value} for user {user_id} "
                f"(success={success})"
            )

            return event

        except Exception as e:
            logger.error(f"Failed to log security event {event_type.value}: {e}")
            # Don't raise - logging failures shouldn't break the application flow
            return None

    @staticmethod
    async def log_2fa_enabled(
        session: AsyncSession,
        user_id: UUID | str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SecurityEvent | None:
        """Log 2FA enabled event."""
        return await SecurityEventService.log_event(
            session=session,
            event_type=SecurityEventType.TWO_FA_ENABLED,
            user_id=user_id,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    async def log_2fa_disabled(
        session: AsyncSession,
        user_id: UUID | str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SecurityEvent | None:
        """Log 2FA disabled event."""
        return await SecurityEventService.log_event(
            session=session,
            event_type=SecurityEventType.TWO_FA_DISABLED,
            user_id=user_id,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    async def log_2fa_setup_initiated(
        session: AsyncSession,
        user_id: UUID | str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SecurityEvent | None:
        """Log 2FA setup initiated event."""
        return await SecurityEventService.log_event(
            session=session,
            event_type=SecurityEventType.TWO_FA_SETUP_INITIATED,
            user_id=user_id,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    async def log_2fa_verification(
        session: AsyncSession,
        user_id: UUID | str,
        success: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> SecurityEvent | None:
        """Log 2FA verification attempt (success or failure)."""
        event_type = (
            SecurityEventType.TWO_FA_VERIFICATION_SUCCESS
            if success
            else SecurityEventType.TWO_FA_VERIFICATION_FAILED
        )
        return await SecurityEventService.log_event(
            session=session,
            event_type=event_type,
            user_id=user_id,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )

    @staticmethod
    async def log_2fa_login(
        session: AsyncSession,
        user_id: UUID | str,
        success: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> SecurityEvent | None:
        """Log 2FA login attempt (success or failure)."""
        event_type = (
            SecurityEventType.TWO_FA_LOGIN_SUCCESS
            if success
            else SecurityEventType.TWO_FA_LOGIN_FAILED
        )
        return await SecurityEventService.log_event(
            session=session,
            event_type=event_type,
            user_id=user_id,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )

    @staticmethod
    async def log_backup_code_used(
        session: AsyncSession,
        user_id: UUID | str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SecurityEvent | None:
        """Log backup code usage."""
        return await SecurityEventService.log_event(
            session=session,
            event_type=SecurityEventType.BACKUP_CODE_USED,
            user_id=user_id,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    async def log_backup_codes_regenerated(
        session: AsyncSession,
        user_id: UUID | str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SecurityEvent | None:
        """Log backup codes regeneration."""
        return await SecurityEventService.log_event(
            session=session,
            event_type=SecurityEventType.BACKUP_CODES_REGENERATED,
            user_id=user_id,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    async def log_password_login(
        session: AsyncSession,
        user_id: UUID | str,
        success: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> SecurityEvent | None:
        """Log password login attempt (success or failure)."""
        event_type = (
            SecurityEventType.PASSWORD_LOGIN_SUCCESS
            if success
            else SecurityEventType.PASSWORD_LOGIN_FAILED
        )
        return await SecurityEventService.log_event(
            session=session,
            event_type=event_type,
            user_id=user_id,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )


# Create a singleton instance
security_event_service = SecurityEventService()
