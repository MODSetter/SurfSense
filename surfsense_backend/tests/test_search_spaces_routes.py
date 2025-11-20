"""
Tests for Search Spaces API endpoints.

Tests cover:
- Creating search spaces
- Reading search spaces (list and detail)
- Updating search spaces
- Deleting search spaces
- Authorization and ownership checks
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSpace, User


@pytest.mark.api
@pytest.mark.asyncio
class TestSearchSpacesRoutes:
    """Test cases for Search Spaces API endpoints."""

    async def test_create_search_space(
        self,
        test_client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
    ):
        """Test creating a new search space."""
        data = {
            "name": "My Test Space",
            "description": "A test search space",
        }

        response = await test_client.post(
            "/searchspaces",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["name"] == data["name"]
        assert result["description"] == data["description"]
        assert result["user_id"] == test_user.id
        assert "id" in result

    async def test_create_search_space_unauthorized(
        self,
        test_client: AsyncClient,
    ):
        """Test creating a search space without authentication."""
        data = {
            "name": "My Test Space",
            "description": "A test search space",
        }

        response = await test_client.post(
            "/searchspaces",
            json=data,
        )

        assert response.status_code == 401

    async def test_create_search_space_missing_required_fields(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """Test creating a search space with missing required fields."""
        data = {
            "description": "Missing name field",
        }

        response = await test_client.post(
            "/searchspaces",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error

    async def test_read_search_spaces_list(
        self,
        test_client: AsyncClient,
        test_user: User,
        test_search_space: SearchSpace,
        auth_headers: dict[str, str],
    ):
        """Test reading list of search spaces."""
        response = await test_client.get(
            "/searchspaces",
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert isinstance(result, list)
        assert len(result) >= 1
        assert any(space["id"] == test_search_space.id for space in result)

    async def test_read_search_spaces_pagination(
        self,
        test_client: AsyncClient,
        async_session: AsyncSession,
        test_user: User,
        auth_headers: dict[str, str],
    ):
        """Test pagination of search spaces."""
        # Create multiple search spaces
        for i in range(5):
            space = SearchSpace(
                name=f"Space {i}",
                description=f"Description {i}",
                user_id=test_user.id,
            )
            async_session.add(space)
        await async_session.commit()

        # Test with limit
        response = await test_client.get(
            "/searchspaces?limit=3",
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert len(result) <= 3

        # Test with skip and limit
        response = await test_client.get(
            "/searchspaces?skip=2&limit=2",
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert len(result) <= 2

    async def test_read_search_spaces_only_own_spaces(
        self,
        test_client: AsyncClient,
        async_session: AsyncSession,
        test_user: User,
        auth_headers: dict[str, str],
    ):
        """Test that users only see their own search spaces."""
        # Create a search space for another user
        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
        )
        async_session.add(other_user)
        await async_session.commit()

        other_space = SearchSpace(
            name="Other User's Space",
            description="Should not be visible",
            user_id=other_user.id,
        )
        async_session.add(other_space)
        await async_session.commit()

        # Request search spaces
        response = await test_client.get(
            "/searchspaces",
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()

        # Verify other user's space is not in results
        assert not any(space["id"] == other_space.id for space in result)

    async def test_read_search_space_by_id(
        self,
        test_client: AsyncClient,
        test_search_space: SearchSpace,
        auth_headers: dict[str, str],
    ):
        """Test reading a specific search space by ID."""
        response = await test_client.get(
            f"/searchspaces/{test_search_space.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["id"] == test_search_space.id
        assert result["name"] == test_search_space.name

    async def test_read_search_space_not_found(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """Test reading a non-existent search space."""
        response = await test_client.get(
            "/searchspaces/999999",
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_read_search_space_unauthorized_access(
        self,
        test_client: AsyncClient,
        async_session: AsyncSession,
        auth_headers: dict[str, str],
    ):
        """Test that users cannot access other users' search spaces."""
        # Create another user and their search space
        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
        )
        async_session.add(other_user)
        await async_session.commit()

        other_space = SearchSpace(
            name="Other User's Space",
            description="Should not be accessible",
            user_id=other_user.id,
        )
        async_session.add(other_space)
        await async_session.commit()

        # Try to access other user's space
        response = await test_client.get(
            f"/searchspaces/{other_space.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404  # Or 403, depending on implementation

    async def test_update_search_space(
        self,
        test_client: AsyncClient,
        test_search_space: SearchSpace,
        auth_headers: dict[str, str],
    ):
        """Test updating a search space."""
        update_data = {
            "name": "Updated Name",
            "description": "Updated description",
        }

        response = await test_client.put(
            f"/searchspaces/{test_search_space.id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["name"] == update_data["name"]
        assert result["description"] == update_data["description"]
        assert result["id"] == test_search_space.id

    async def test_update_search_space_partial(
        self,
        test_client: AsyncClient,
        test_search_space: SearchSpace,
        auth_headers: dict[str, str],
    ):
        """Test partial update of a search space."""
        original_name = test_search_space.name

        update_data = {
            "description": "Only updating description",
        }

        response = await test_client.put(
            f"/searchspaces/{test_search_space.id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["name"] == original_name  # Name unchanged
        assert result["description"] == update_data["description"]

    async def test_update_search_space_not_found(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """Test updating a non-existent search space."""
        update_data = {
            "name": "Updated Name",
        }

        response = await test_client.put(
            "/searchspaces/999999",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_update_search_space_unauthorized(
        self,
        test_client: AsyncClient,
        async_session: AsyncSession,
        auth_headers: dict[str, str],
    ):
        """Test that users cannot update other users' search spaces."""
        # Create another user and their search space
        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
        )
        async_session.add(other_user)
        await async_session.commit()

        other_space = SearchSpace(
            name="Other User's Space",
            description="Should not be updatable",
            user_id=other_user.id,
        )
        async_session.add(other_space)
        await async_session.commit()

        update_data = {
            "name": "Hacked Name",
        }

        response = await test_client.put(
            f"/searchspaces/{other_space.id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 404  # Or 403

    async def test_delete_search_space(
        self,
        test_client: AsyncClient,
        async_session: AsyncSession,
        test_user: User,
        auth_headers: dict[str, str],
    ):
        """Test deleting a search space."""
        # Create a search space to delete
        space = SearchSpace(
            name="Space to Delete",
            description="This will be deleted",
            user_id=test_user.id,
        )
        async_session.add(space)
        await async_session.commit()
        await async_session.refresh(space)
        space_id = space.id

        response = await test_client.delete(
            f"/searchspaces/{space_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert "message" in result
        assert "deleted" in result["message"].lower()

        # Verify space is actually deleted
        from sqlalchemy.future import select

        result = await async_session.execute(
            select(SearchSpace).filter(SearchSpace.id == space_id)
        )
        deleted_space = result.scalar_one_or_none()
        assert deleted_space is None

    async def test_delete_search_space_not_found(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """Test deleting a non-existent search space."""
        response = await test_client.delete(
            "/searchspaces/999999",
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_delete_search_space_unauthorized(
        self,
        test_client: AsyncClient,
        async_session: AsyncSession,
        auth_headers: dict[str, str],
    ):
        """Test that users cannot delete other users' search spaces."""
        # Create another user and their search space
        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
        )
        async_session.add(other_user)
        await async_session.commit()

        other_space = SearchSpace(
            name="Other User's Space",
            description="Should not be deletable",
            user_id=other_user.id,
        )
        async_session.add(other_space)
        await async_session.commit()

        response = await test_client.delete(
            f"/searchspaces/{other_space.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404  # Or 403

        # Verify space still exists
        from sqlalchemy.future import select

        result = await async_session.execute(
            select(SearchSpace).filter(SearchSpace.id == other_space.id)
        )
        existing_space = result.scalar_one_or_none()
        assert existing_space is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestSearchSpacesIntegration:
    """Integration tests for search spaces workflow."""

    async def test_complete_crud_workflow(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """Test complete CRUD workflow for search spaces."""
        # Create
        create_data = {
            "name": "Workflow Test Space",
            "description": "Testing complete workflow",
        }
        create_response = await test_client.post(
            "/searchspaces",
            json=create_data,
            headers=auth_headers,
        )
        assert create_response.status_code == 200
        created = create_response.json()
        space_id = created["id"]

        # Read (detail)
        read_response = await test_client.get(
            f"/searchspaces/{space_id}",
            headers=auth_headers,
        )
        assert read_response.status_code == 200
        assert read_response.json()["name"] == create_data["name"]

        # Update
        update_data = {"name": "Updated Workflow Space"}
        update_response = await test_client.put(
            f"/searchspaces/{space_id}",
            json=update_data,
            headers=auth_headers,
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == update_data["name"]

        # Delete
        delete_response = await test_client.delete(
            f"/searchspaces/{space_id}",
            headers=auth_headers,
        )
        assert delete_response.status_code == 200

        # Verify deletion
        read_after_delete = await test_client.get(
            f"/searchspaces/{space_id}",
            headers=auth_headers,
        )
        assert read_after_delete.status_code == 404
