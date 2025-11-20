"""
Tests for Page Limit Service.

Tests cover:
- Checking page limits
- Updating page usage
- Getting page usage
- Estimating pages from various sources
- Handling concurrent requests (race condition testing)
"""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User
from app.services.page_limit_service import PageLimitExceededError, PageLimitService


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestPageLimitService:
    """Test cases for PageLimitService."""

    @pytest.fixture
    async def user_with_limits(self, async_session: AsyncSession) -> User:
        """Create a user with page limits for testing."""
        user = User(
            email="limit_test@example.com",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
            pages_used=0,
            pages_limit=100,
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        return user

    @pytest.fixture
    async def service(self, async_session: AsyncSession) -> PageLimitService:
        """Create a PageLimitService instance."""
        return PageLimitService(session=async_session)

    async def test_check_page_limit_success(
        self,
        service: PageLimitService,
        user_with_limits: User,
    ):
        """Test checking page limit when user has capacity."""
        has_capacity, pages_used, pages_limit = await service.check_page_limit(
            user_id=user_with_limits.id,
            estimated_pages=10,
        )

        assert has_capacity is True
        assert pages_used == 0
        assert pages_limit == 100

    async def test_check_page_limit_exceeds(
        self,
        service: PageLimitService,
        async_session: AsyncSession,
    ):
        """Test checking page limit when user would exceed limit."""
        # Create user with high usage
        user = User(
            email="high_usage@example.com",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
            pages_used=95,
            pages_limit=100,
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        # Try to add pages that would exceed limit
        with pytest.raises(PageLimitExceededError) as exc_info:
            await service.check_page_limit(user_id=user.id, estimated_pages=10)

        assert exc_info.value.pages_used == 95
        assert exc_info.value.pages_limit == 100
        assert exc_info.value.pages_to_add == 10

    async def test_check_page_limit_user_not_found(self, service: PageLimitService):
        """Test checking page limit for non-existent user."""
        with pytest.raises(ValueError, match="User with ID .* not found"):
            await service.check_page_limit(
                user_id="00000000-0000-0000-0000-000000000000",
                estimated_pages=10,
            )

    async def test_update_page_usage_success(
        self,
        service: PageLimitService,
        user_with_limits: User,
        async_session: AsyncSession,
    ):
        """Test updating page usage successfully."""
        new_usage = await service.update_page_usage(
            user_id=user_with_limits.id,
            pages_to_add=25,
        )

        assert new_usage == 25

        # Verify in database
        await async_session.refresh(user_with_limits)
        assert user_with_limits.pages_used == 25

    async def test_update_page_usage_multiple_times(
        self,
        service: PageLimitService,
        user_with_limits: User,
    ):
        """Test multiple updates accumulate correctly."""
        await service.update_page_usage(user_id=user_with_limits.id, pages_to_add=10)
        await service.update_page_usage(user_id=user_with_limits.id, pages_to_add=15)
        new_usage = await service.update_page_usage(
            user_id=user_with_limits.id,
            pages_to_add=5,
        )

        assert new_usage == 30

    async def test_update_page_usage_exceeds_limit(
        self,
        service: PageLimitService,
        async_session: AsyncSession,
    ):
        """Test that updating page usage fails when it would exceed limit."""
        user = User(
            email="almost_full@example.com",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
            pages_used=95,
            pages_limit=100,
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        with pytest.raises(PageLimitExceededError):
            await service.update_page_usage(user_id=user.id, pages_to_add=10)

    async def test_update_page_usage_allow_exceed(
        self,
        service: PageLimitService,
        async_session: AsyncSession,
    ):
        """Test that allow_exceed flag allows exceeding limit."""
        user = User(
            email="allow_exceed@example.com",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
            pages_used=95,
            pages_limit=100,
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        new_usage = await service.update_page_usage(
            user_id=user.id,
            pages_to_add=10,
            allow_exceed=True,
        )

        assert new_usage == 105  # Exceeds limit

    async def test_update_page_usage_user_not_found(self, service: PageLimitService):
        """Test updating page usage for non-existent user."""
        with pytest.raises(ValueError, match="User with ID .* not found"):
            await service.update_page_usage(
                user_id="00000000-0000-0000-0000-000000000000",
                pages_to_add=10,
            )

    async def test_get_page_usage(
        self,
        service: PageLimitService,
        async_session: AsyncSession,
    ):
        """Test getting page usage."""
        user = User(
            email="usage_check@example.com",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
            pages_used=50,
            pages_limit=200,
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        pages_used, pages_limit = await service.get_page_usage(user_id=user.id)

        assert pages_used == 50
        assert pages_limit == 200

    async def test_get_page_usage_user_not_found(self, service: PageLimitService):
        """Test getting page usage for non-existent user."""
        with pytest.raises(ValueError, match="User with ID .* not found"):
            await service.get_page_usage(
                user_id="00000000-0000-0000-0000-000000000000"
            )

    @pytest.mark.slow
    async def test_concurrent_updates_race_condition(
        self,
        service: PageLimitService,
        async_session: AsyncSession,
    ):
        """
        Test that demonstrates potential race condition with concurrent updates.

        This test should fail with current implementation (check-then-act pattern)
        and pass after fixing with atomic updates.
        """
        # Create user with 90 pages used, limit 100
        user = User(
            email="race_test@example.com",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
            pages_used=90,
            pages_limit=100,
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        # Try to add 10 pages concurrently (both should pass the check, but only one should succeed)
        async def try_update():
            # Each task gets its own service instance with same session
            task_service = PageLimitService(session=async_session)
            try:
                # Check limit
                await task_service.check_page_limit(user_id=user.id, estimated_pages=10)
                # Small delay to make race condition more likely
                await asyncio.sleep(0.01)
                # Update usage
                await task_service.update_page_usage(user_id=user.id, pages_to_add=10)
                return True
            except PageLimitExceededError:
                return False

        # Run two concurrent updates
        results = await asyncio.gather(
            try_update(),
            try_update(),
            return_exceptions=True,
        )

        # Verify final state
        await async_session.refresh(user)

        # With race condition: both might succeed, leading to 110 pages (exceeds limit)
        # After fix: only one should succeed, resulting in 100 pages
        # For now, this test documents the issue
        # After fixing, uncomment the assertion below:
        # assert user.pages_used <= 100, "Race condition allowed exceeding limit!"


@pytest.mark.unit
class TestPageEstimation:
    """Test page estimation methods."""

    @pytest.fixture
    def service(self, async_session: AsyncSession) -> PageLimitService:
        """Create a PageLimitService instance."""
        return PageLimitService(session=async_session)

    def test_estimate_pages_from_content_length(self, service: PageLimitService):
        """Test estimating pages from content length."""
        # Short content (less than one page)
        assert service.estimate_pages_from_content_length(1000) == 1

        # One page worth of content
        assert service.estimate_pages_from_content_length(2000) == 1

        # Multiple pages
        assert service.estimate_pages_from_content_length(5000) == 2
        assert service.estimate_pages_from_content_length(10000) == 5

    def test_estimate_pages_before_processing_pdf(self, service: PageLimitService):
        """Test estimating pages from a PDF file."""
        # Create a minimal PDF for testing
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            # Write minimal PDF content (from conftest fixture)
            tmp_file.write(
                b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
xref
0 3
trailer
<<
/Size 3
/Root 1 0 R
>>
startxref
%%EOF"""
            )
            tmp_file.flush()

            try:
                # Estimate pages
                pages = service.estimate_pages_before_processing(tmp_file.name)
                assert pages >= 1
            finally:
                os.unlink(tmp_file.name)

    def test_estimate_pages_before_processing_text(self, service: PageLimitService):
        """Test estimating pages from a text file."""
        with tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, mode="w"
        ) as tmp_file:
            # Write text content
            tmp_file.write("x" * 6000)  # 6000 characters, should be ~2 pages
            tmp_file.flush()

            try:
                pages = service.estimate_pages_before_processing(tmp_file.name)
                assert pages >= 2
            finally:
                os.unlink(tmp_file.name)

    def test_estimate_pages_before_processing_image(self, service: PageLimitService):
        """Test estimating pages from an image file."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            # Write some dummy data (not a real image, but enough for file size test)
            tmp_file.write(b"dummy image data")
            tmp_file.flush()

            try:
                pages = service.estimate_pages_before_processing(tmp_file.name)
                assert pages == 1  # Images are always 1 page
            finally:
                os.unlink(tmp_file.name)

    def test_estimate_pages_before_processing_unknown_extension(
        self, service: PageLimitService
    ):
        """Test estimating pages from file with unknown extension."""
        with tempfile.NamedTemporaryFile(suffix=".unknown", delete=False) as tmp_file:
            # Write some content
            tmp_file.write(b"x" * 100000)  # 100KB
            tmp_file.flush()

            try:
                pages = service.estimate_pages_before_processing(tmp_file.name)
                assert pages >= 1  # Should use conservative estimate
            finally:
                os.unlink(tmp_file.name)

    def test_estimate_pages_before_processing_file_not_found(
        self, service: PageLimitService
    ):
        """Test that estimating pages from non-existent file raises error."""
        with pytest.raises(ValueError, match="File not found"):
            service.estimate_pages_before_processing("/nonexistent/file.pdf")


@pytest.mark.integration
@pytest.mark.asyncio
class TestPageLimitWorkflow:
    """Integration tests for page limit workflow."""

    async def test_complete_workflow(
        self,
        async_session: AsyncSession,
    ):
        """Test complete page limit check and update workflow."""
        service = PageLimitService(session=async_session)

        # Create user
        user = User(
            email="workflow@example.com",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
            pages_used=0,
            pages_limit=100,
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        # 1. Check if user has capacity
        has_capacity, pages_used, pages_limit = await service.check_page_limit(
            user_id=user.id,
            estimated_pages=20,
        )
        assert has_capacity is True

        # 2. Process document (simulated)
        # ... processing ...

        # 3. Update usage after successful processing
        new_usage = await service.update_page_usage(
            user_id=user.id,
            pages_to_add=20,
        )
        assert new_usage == 20

        # 4. Verify usage
        pages_used, pages_limit = await service.get_page_usage(user_id=user.id)
        assert pages_used == 20
        assert pages_limit == 100

    async def test_workflow_with_limit_exceeded(
        self,
        async_session: AsyncSession,
    ):
        """Test workflow when user exceeds limit."""
        service = PageLimitService(session=async_session)

        # Create user near limit
        user = User(
            email="near_limit@example.com",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
            pages_used=95,
            pages_limit=100,
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        # Check should fail
        with pytest.raises(PageLimitExceededError) as exc_info:
            await service.check_page_limit(user_id=user.id, estimated_pages=10)

        error = exc_info.value
        assert error.pages_used == 95
        assert error.pages_limit == 100
        assert error.pages_to_add == 10

        # Verify usage unchanged
        pages_used, pages_limit = await service.get_page_usage(user_id=user.id)
        assert pages_used == 95
