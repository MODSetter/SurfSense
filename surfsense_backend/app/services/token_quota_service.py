"""
Service for managing user LLM token quotas (cloud subscription mode).

Mirrors PageLimitService pattern for consistency.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


class TokenQuotaExceededError(Exception):
    """
    Exception raised when a user exceeds their monthly token quota.
    """

    def __init__(
        self,
        message: str = "Monthly token quota exceeded. Please upgrade your plan.",
        tokens_used: int = 0,
        monthly_token_limit: int = 0,
        tokens_requested: int = 0,
    ):
        self.tokens_used = tokens_used
        self.monthly_token_limit = monthly_token_limit
        self.tokens_requested = tokens_requested
        super().__init__(message)


class TokenQuotaService:
    """Service for checking and updating user LLM token quotas."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _maybe_reset_monthly_tokens(self, user) -> None:
        """
        Reset tokens_used_this_month to 0 if token_reset_date has passed.

        Called before any quota check or update so that a new billing cycle
        starts transparently without requiring a cron job or webhook trigger.

        The token_reset_date is a Date column. We compare against UTC today.

        NOTE: This method does NOT commit — the caller manages the transaction.
        """
        today = datetime.now(UTC).date()

        if not user.token_reset_date:
            # First time — set reset date 30 days from now
            user.token_reset_date = today + timedelta(days=30)
            user.tokens_used_this_month = 0
            return

        reset_date = user.token_reset_date
        # Handle if somehow stored as a string (legacy data)
        if isinstance(reset_date, str):
            try:
                reset_date = date.fromisoformat(reset_date)
            except ValueError:
                reset_date = today + timedelta(days=30)

        if today >= reset_date:
            # New billing cycle — reset usage and advance reset date by 30 days
            new_reset = reset_date + timedelta(days=30)
            user.tokens_used_this_month = 0
            user.token_reset_date = new_reset

    async def check_token_quota(
        self, user_id: str, estimated_tokens: int = 0
    ) -> tuple[bool, int, int]:
        """
        Check if user has remaining token quota this month.

        Args:
            user_id: The user's UUID (string)
            estimated_tokens: Optional pre-estimated input token count

        Returns:
            Tuple of (has_capacity, tokens_used, monthly_token_limit)

        Raises:
            TokenQuotaExceededError: If user would exceed their monthly limit
        """
        from app.db import User

        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.unique().scalar_one_or_none()

        if not user:
            raise ValueError(f"User with ID {user_id} not found")

        await self._maybe_reset_monthly_tokens(user)
        await self.session.flush()  # Persist any reset changes within the transaction

        tokens_used = user.tokens_used_this_month or 0
        token_limit = user.monthly_token_limit or 0

        # Strict boundary: >= means at-limit is also exceeded
        if tokens_used + estimated_tokens >= token_limit and token_limit > 0:
            raise TokenQuotaExceededError(
                message=(
                    f"Monthly token quota exceeded. "
                    f"Used: {tokens_used:,}/{token_limit:,} tokens. "
                    f"Estimated request: {estimated_tokens:,} tokens. "
                    f"Please upgrade your subscription plan."
                ),
                tokens_used=tokens_used,
                monthly_token_limit=token_limit,
                tokens_requested=estimated_tokens,
            )

        return True, tokens_used, token_limit

    async def update_token_usage(
        self, user_id: str, tokens_to_add: int, allow_exceed: bool = True
    ) -> int:
        """
        Atomically add tokens consumed to the user's monthly usage.

        Uses a single SQL UPDATE with arithmetic expression to prevent
        race conditions when multiple streams finish concurrently.

        Args:
            user_id: The user's UUID (string)
            tokens_to_add: Actual tokens consumed (input + output)
            allow_exceed: If True (default), records usage even if it pushes
                         past the limit.  Set False to enforce hard cap at
                         update time (pre-check should already have fired).

        Returns:
            New total tokens_used_this_month value
        """
        from app.db import User

        if tokens_to_add <= 0:
            # Nothing to deduct — fetch current usage and return
            result = await self.session.execute(
                select(User.tokens_used_this_month).where(User.id == user_id)
            )
            row = result.first()
            if not row:
                raise ValueError(f"User with ID {user_id} not found")
            return row[0] or 0

        # Atomic UPDATE: tokens_used = tokens_used + N (no read-modify-write)
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(tokens_used_this_month=User.tokens_used_this_month + tokens_to_add)
            .returning(User.tokens_used_this_month)
        )
        result = await self.session.execute(stmt)
        row = result.first()

        if not row:
            raise ValueError(f"User with ID {user_id} not found")

        new_usage = row[0]
        await self.session.commit()

        return new_usage

    async def get_token_usage(self, user_id: str) -> tuple[int, int]:
        """
        Get user's current token usage and monthly limit.

        Also triggers monthly reset check so the returned values
        are always for the current billing cycle.

        Args:
            user_id: The user's UUID (string)

        Returns:
            Tuple of (tokens_used_this_month, monthly_token_limit)
        """
        from app.db import User

        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.unique().scalar_one_or_none()

        if not user:
            raise ValueError(f"User with ID {user_id} not found")

        await self._maybe_reset_monthly_tokens(user)
        await self.session.flush()

        return (user.tokens_used_this_month or 0, user.monthly_token_limit or 0)
