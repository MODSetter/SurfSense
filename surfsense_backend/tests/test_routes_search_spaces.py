"""
Tests for search spaces routes.
Tests API endpoints with mocked database sessions and authentication.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.routes.search_spaces_routes import (
    create_search_space,
    read_search_spaces,
    read_search_space,
    update_search_space,
    delete_search_space,
    create_default_roles_and_membership,
)
from app.schemas import SearchSpaceCreate, SearchSpaceUpdate


class TestCreateDefaultRolesAndMembership:
    """Tests for the create_default_roles_and_membership helper function."""

    @pytest.mark.asyncio
    async def test_creates_default_roles(self):
        """Test that default roles are created for a search space."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        
        with patch("app.routes.search_spaces_routes.get_default_roles_config") as mock_get_roles:
            mock_get_roles.return_value = [
                {
                    "name": "Owner",
                    "description": "Full access",
                    "permissions": ["*"],
                    "is_default": False,
                    "is_system_role": True,
                },
                {
                    "name": "Editor",
                    "description": "Can edit",
                    "permissions": ["documents:create"],
                    "is_default": True,
                    "is_system_role": True,
                },
            ]
            
            await create_default_roles_and_membership(
                mock_session,
                search_space_id=1,
                owner_user_id="user-123",
            )
            
            # Should add roles and membership
            assert mock_session.add.call_count >= 2
            assert mock_session.flush.call_count >= 1


class TestCreateSearchSpace:
    """Tests for the create_search_space endpoint."""

    @pytest.mark.asyncio
    async def test_create_search_space_success(self):
        """Test successful search space creation."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        search_space_data = SearchSpaceCreate(name="Test Space")
        
        with patch("app.routes.search_spaces_routes.create_default_roles_and_membership") as mock_create_roles:
            mock_create_roles.return_value = None
            
            # Mock the SearchSpace class
            with patch("app.routes.search_spaces_routes.SearchSpace") as MockSearchSpace:
                mock_search_space = MagicMock()
                mock_search_space.id = 1
                mock_search_space.name = "Test Space"
                MockSearchSpace.return_value = mock_search_space
                
                await create_search_space(
                    search_space=search_space_data,
                    session=mock_session,
                    user=mock_user,
                )
                
                assert mock_session.add.called
                assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_create_search_space_database_error(self):
        """Test search space creation handles database errors."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock(side_effect=Exception("Database error"))
        mock_session.rollback = AsyncMock()
        
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        search_space_data = SearchSpaceCreate(name="Test Space")
        
        with pytest.raises(HTTPException) as exc_info:
            await create_search_space(
                search_space=search_space_data,
                session=mock_session,
                user=mock_user,
            )
        
        assert exc_info.value.status_code == 500


class TestReadSearchSpaces:
    """Tests for the read_search_spaces endpoint."""

    @pytest.mark.asyncio
    async def test_read_search_spaces_owned_only(self):
        """Test reading only owned search spaces."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock the query result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        result = await read_search_spaces(
            skip=0,
            limit=200,
            owned_only=True,
            session=mock_session,
            user=mock_user,
        )
        
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_read_search_spaces_all_accessible(self):
        """Test reading all accessible search spaces."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock the query result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar.return_value = 0
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        result = await read_search_spaces(
            skip=0,
            limit=200,
            owned_only=False,
            session=mock_session,
            user=mock_user,
        )
        
        assert isinstance(result, list)


class TestReadSearchSpace:
    """Tests for the read_search_space endpoint."""

    @pytest.mark.asyncio
    async def test_read_search_space_not_found(self):
        """Test reading non-existent search space."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock empty result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        with patch("app.routes.search_spaces_routes.check_search_space_access") as mock_check:
            mock_check.return_value = None
            
            with pytest.raises(HTTPException) as exc_info:
                await read_search_space(
                    search_space_id=999,
                    session=mock_session,
                    user=mock_user,
                )
            
            assert exc_info.value.status_code == 404


class TestUpdateSearchSpace:
    """Tests for the update_search_space endpoint."""

    @pytest.mark.asyncio
    async def test_update_search_space_not_found(self):
        """Test updating non-existent search space."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock empty result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.rollback = AsyncMock()
        
        update_data = SearchSpaceUpdate(name="Updated Name")
        
        with patch("app.routes.search_spaces_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            with pytest.raises(HTTPException) as exc_info:
                await update_search_space(
                    search_space_id=999,
                    search_space_update=update_data,
                    session=mock_session,
                    user=mock_user,
                )
            
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_search_space_success(self):
        """Test successful search space update."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock existing search space
        mock_search_space = MagicMock()
        mock_search_space.id = 1
        mock_search_space.name = "Old Name"
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_search_space
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        update_data = SearchSpaceUpdate(name="New Name")
        
        with patch("app.routes.search_spaces_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            await update_search_space(
                search_space_id=1,
                search_space_update=update_data,
                session=mock_session,
                user=mock_user,
            )
            
            assert mock_session.commit.called


class TestDeleteSearchSpace:
    """Tests for the delete_search_space endpoint."""

    @pytest.mark.asyncio
    async def test_delete_search_space_not_found(self):
        """Test deleting non-existent search space."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock empty result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.rollback = AsyncMock()
        
        with patch("app.routes.search_spaces_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            with pytest.raises(HTTPException) as exc_info:
                await delete_search_space(
                    search_space_id=999,
                    session=mock_session,
                    user=mock_user,
                )
            
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_search_space_success(self):
        """Test successful search space deletion."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock existing search space
        mock_search_space = MagicMock()
        mock_search_space.id = 1
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_search_space
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()
        
        with patch("app.routes.search_spaces_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            result = await delete_search_space(
                search_space_id=1,
                session=mock_session,
                user=mock_user,
            )
            
            assert result["message"] == "Search space deleted successfully"
            assert mock_session.delete.called
            assert mock_session.commit.called
