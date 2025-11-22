"""
Comprehensive tests for space sharing and permissions functionality.

CRITICAL SECURITY: These tests verify that public spaces are read-only for non-owners
and that only superusers can share spaces.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

# Test configuration - these fixtures should be defined in conftest.py:
# - client: TestClient
# - normal_user_token: str (token for a normal user)
# - another_user_token: str (token for a different normal user)
# - superuser_token: str (token for a superuser)
# - test_space_id: int (a test search space owned by normal_user)
# - public_space_id: int (a public search space)


class TestSpaceSharing:
    """Tests for the POST /searchspaces/{id}/share endpoint"""

    def test_share_space_requires_authentication(self, client: TestClient):
        """Unauthenticated requests should fail with 401"""
        response = client.post("/api/v1/searchspaces/1/share")
        assert response.status_code == 401

    def test_share_space_requires_superuser(
        self, client: TestClient, normal_user_token: str, test_space_id: int
    ):
        """Non-superuser should not be able to share spaces"""
        response = client.post(
            f"/api/v1/searchspaces/{test_space_id}/share",
            headers={"Authorization": f"Bearer {normal_user_token}"}
        )
        assert response.status_code == 403
        assert "administrator" in response.json()["detail"].lower()

    def test_share_space_success(
        self, client: TestClient, superuser_token: str, test_space_id: int
    ):
        """Superuser should successfully share a space"""
        response = client.post(
            f"/api/v1/searchspaces/{test_space_id}/share",
            headers={"Authorization": f"Bearer {superuser_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_public"] is True
        assert data["search_space_id"] == test_space_id
        assert "successfully" in data["message"].lower()

    def test_share_nonexistent_space(
        self, client: TestClient, superuser_token: str
    ):
        """Sharing a non-existent space should return 404"""
        response = client.post(
            "/api/v1/searchspaces/99999/share",
            headers={"Authorization": f"Bearer {superuser_token}"}
        )
        assert response.status_code == 404


class TestPublicSpaceDiscovery:
    """Tests for GET /searchspaces endpoint with public spaces"""

    def test_public_spaces_visible_to_all_users(
        self,
        client: TestClient,
        another_user_token: str,
        public_space_id: int
    ):
        """Public spaces should appear in any authenticated user's space list"""
        response = client.get(
            "/api/v1/searchspaces",
            headers={"Authorization": f"Bearer {another_user_token}"}
        )
        assert response.status_code == 200
        spaces = response.json()

        # Check if the public space is in the list
        public_space_ids = [s["id"] for s in spaces if s.get("is_public")]
        assert public_space_id in public_space_ids

    def test_private_spaces_not_visible_to_other_users(
        self,
        client: TestClient,
        another_user_token: str,
        test_space_id: int  # private space owned by normal_user
    ):
        """Private spaces should not appear in other users' space lists"""
        response = client.get(
            "/api/v1/searchspaces",
            headers={"Authorization": f"Bearer {another_user_token}"}
        )
        assert response.status_code == 200
        spaces = response.json()

        # Check that the private space is NOT in the list
        space_ids = [s["id"] for s in spaces]
        assert test_space_id not in space_ids

    def test_owner_sees_own_private_spaces(
        self,
        client: TestClient,
        normal_user_token: str,
        test_space_id: int
    ):
        """Owners should see their own private spaces"""
        response = client.get(
            "/api/v1/searchspaces",
            headers={"Authorization": f"Bearer {normal_user_token}"}
        )
        assert response.status_code == 200
        spaces = response.json()

        space_ids = [s["id"] for s in spaces]
        assert test_space_id in space_ids


class TestPublicSpaceReadAccess:
    """Tests for viewing individual public spaces"""

    def test_public_space_viewable_by_non_owner(
        self,
        client: TestClient,
        another_user_token: str,
        public_space_id: int
    ):
        """Any authenticated user should be able to view a public space"""
        response = client.get(
            f"/api/v1/searchspaces/{public_space_id}",
            headers={"Authorization": f"Bearer {another_user_token}"}
        )
        assert response.status_code == 200
        space = response.json()
        assert space["id"] == public_space_id
        assert space["is_public"] is True

    def test_private_space_not_viewable_by_non_owner(
        self,
        client: TestClient,
        another_user_token: str,
        test_space_id: int
    ):
        """Non-owners should not be able to view private spaces"""
        response = client.get(
            f"/api/v1/searchspaces/{test_space_id}",
            headers={"Authorization": f"Bearer {another_user_token}"}
        )
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()


class TestPublicSpaceWriteProtection:
    """CRITICAL SECURITY: Tests that public spaces are read-only for non-owners"""

    def test_cannot_add_documents_to_public_space(
        self,
        client: TestClient,
        another_user_token: str,
        public_space_id: int
    ):
        """Non-owner should not be able to add documents to public space"""
        response = client.post(
            "/api/v1/documents",
            json={
                "search_space_id": public_space_id,
                "document_type": "CRAWLED_URL",
                "content": ["https://example.com"]
            },
            headers={"Authorization": f"Bearer {another_user_token}"}
        )
        assert response.status_code == 403
        assert "read-only" in response.json()["detail"].lower()

    def test_cannot_upload_files_to_public_space(
        self,
        client: TestClient,
        another_user_token: str,
        public_space_id: int
    ):
        """Non-owner should not be able to upload files to public space"""
        response = client.post(
            "/api/v1/documents/fileupload",
            data={"search_space_id": str(public_space_id)},
            files={"files": ("test.txt", b"test content", "text/plain")},
            headers={"Authorization": f"Bearer {another_user_token}"}
        )
        assert response.status_code == 403
        assert "read-only" in response.json()["detail"].lower()

    def test_cannot_create_connector_in_public_space(
        self,
        client: TestClient,
        another_user_token: str,
        public_space_id: int
    ):
        """Non-owner should not be able to create connectors in public space"""
        response = client.post(
            f"/api/v1/search-source-connectors?search_space_id={public_space_id}",
            json={
                "name": "Test Connector",
                "connector_type": "SLACK_CONNECTOR",
                "is_indexable": True,
                "config": {"SLACK_BOT_TOKEN": "test-token"}
            },
            headers={"Authorization": f"Bearer {another_user_token}"}
        )
        assert response.status_code == 403
        assert "read-only" in response.json()["detail"].lower()

    def test_cannot_index_connector_in_public_space(
        self,
        client: TestClient,
        another_user_token: str,
        public_space_id: int,
        public_space_connector_id: int  # Connector in the public space
    ):
        """Non-owner should not be able to trigger indexing in public space"""
        response = client.post(
            f"/api/v1/search-source-connectors/{public_space_connector_id}/index",
            params={"search_space_id": public_space_id},
            headers={"Authorization": f"Bearer {another_user_token}"}
        )
        assert response.status_code == 403
        assert "read-only" in response.json()["detail"].lower()

    def test_owner_can_still_modify_public_space(
        self,
        client: TestClient,
        normal_user_token: str,
        public_space_id: int
    ):
        """Owner should still be able to modify their own public space"""
        response = client.post(
            "/api/v1/documents",
            json={
                "search_space_id": public_space_id,
                "document_type": "CRAWLED_URL",
                "content": ["https://example.com"]
            },
            headers={"Authorization": f"Bearer {normal_user_token}"}
        )
        # Should succeed (200) or be accepted for processing (202)
        assert response.status_code in [200, 202]

    def test_superuser_can_modify_any_public_space(
        self,
        client: TestClient,
        superuser_token: str,
        public_space_id: int
    ):
        """Superuser should be able to modify any space (even public ones they don't own)"""
        response = client.post(
            "/api/v1/documents",
            json={
                "search_space_id": public_space_id,
                "document_type": "CRAWLED_URL",
                "content": ["https://example.com"]
            },
            headers={"Authorization": f"Bearer {superuser_token}"}
        )
        # Should succeed
        assert response.status_code in [200, 202]


class TestDatabaseMigration:
    """Tests to verify database schema correctness"""

    @pytest.mark.asyncio
    async def test_is_public_field_exists(self, async_session: AsyncSession):
        """Verify that is_public field exists in database"""
        from sqlalchemy import text

        result = await async_session.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'searchspaces'
                AND column_name = 'is_public'
            """)
        )
        column = result.fetchone()
        assert column is not None, "is_public column does not exist"

    @pytest.mark.asyncio
    async def test_no_null_is_public_values(self, async_session: AsyncSession):
        """Verify that all search spaces have is_public set (no NULLs)"""
        from sqlalchemy import text

        result = await async_session.execute(
            text("SELECT COUNT(*) FROM searchspaces WHERE is_public IS NULL")
        )
        null_count = result.scalar()
        assert null_count == 0, f"Found {null_count} search spaces with NULL is_public"

    @pytest.mark.asyncio
    async def test_indexes_exist(self, async_session: AsyncSession):
        """Verify that required indexes exist"""
        from sqlalchemy import text

        result = await async_session.execute(
            text("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'searchspaces'
                AND indexname IN ('ix_searchspaces_is_public', 'ix_searchspaces_user_public')
            """)
        )
        indexes = [row[0] for row in result.fetchall()]

        assert 'ix_searchspaces_is_public' in indexes, "Index ix_searchspaces_is_public missing"
        assert 'ix_searchspaces_user_public' in indexes, "Index ix_searchspaces_user_public missing"


# Pytest fixtures configuration (to be added to conftest.py)
"""
# Add these fixtures to surfsense_backend/tests/conftest.py:

@pytest.fixture
def normal_user_token(test_db):
    # Create a normal user and return their JWT token
    pass

@pytest.fixture
def another_user_token(test_db):
    # Create another normal user and return their JWT token
    pass

@pytest.fixture
def superuser_token(test_db):
    # Create a superuser and return their JWT token
    pass

@pytest.fixture
def test_space_id(test_db, normal_user):
    # Create a test search space owned by normal_user
    # Return the space ID
    pass

@pytest.fixture
def public_space_id(test_db, normal_user):
    # Create a public search space (is_public=True) owned by normal_user
    # Return the space ID
    pass

@pytest.fixture
def public_space_connector_id(test_db, public_space_id):
    # Create a connector in the public space
    # Return the connector ID
    pass
"""
