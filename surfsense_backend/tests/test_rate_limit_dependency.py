"""
Tests for rate limiting dependency.

Tests cover:
- IP address extraction from various headers
- Reverse proxy header handling
- Rate limit blocking behavior
"""

import pytest
from fastapi import FastAPI, Depends
from httpx import AsyncClient
from unittest.mock import MagicMock, patch

from app.dependencies.rate_limit import check_rate_limit, get_client_ip


@pytest.mark.unit
class TestGetClientIP:
    """Test cases for get_client_ip function."""

    def test_get_ip_from_x_forwarded_for(self):
        """Test extracting IP from X-Forwarded-For header."""
        request = MagicMock()
        request.headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8, 9.10.11.12"}
        request.client = None

        ip = get_client_ip(request)

        # Should return the first IP (client IP), not proxy IPs
        assert ip == "1.2.3.4"

    def test_get_ip_from_x_forwarded_for_single(self):
        """Test extracting single IP from X-Forwarded-For."""
        request = MagicMock()
        request.headers = {"x-forwarded-for": "1.2.3.4"}
        request.client = None

        ip = get_client_ip(request)

        assert ip == "1.2.3.4"

    def test_get_ip_from_x_forwarded_for_with_spaces(self):
        """Test extracting IP from X-Forwarded-For with extra spaces."""
        request = MagicMock()
        request.headers = {"x-forwarded-for": "  1.2.3.4  ,  5.6.7.8  "}
        request.client = None

        ip = get_client_ip(request)

        # Should strip whitespace
        assert ip == "1.2.3.4"

    def test_get_ip_from_x_real_ip(self):
        """Test extracting IP from X-Real-IP header."""
        request = MagicMock()
        request.headers = {"x-real-ip": "1.2.3.4"}
        request.client = None

        ip = get_client_ip(request)

        assert ip == "1.2.3.4"

    def test_x_forwarded_for_takes_precedence(self):
        """Test that X-Forwarded-For takes precedence over X-Real-IP."""
        request = MagicMock()
        request.headers = {
            "x-forwarded-for": "1.2.3.4",
            "x-real-ip": "5.6.7.8",
        }
        request.client = MagicMock()
        request.client.host = "9.10.11.12"

        ip = get_client_ip(request)

        # Should use X-Forwarded-For (highest priority)
        assert ip == "1.2.3.4"

    def test_x_real_ip_takes_precedence_over_client(self):
        """Test that X-Real-IP takes precedence over request.client."""
        request = MagicMock()
        request.headers = {"x-real-ip": "1.2.3.4"}
        request.client = MagicMock()
        request.client.host = "5.6.7.8"

        ip = get_client_ip(request)

        # Should use X-Real-IP
        assert ip == "1.2.3.4"

    def test_get_ip_from_direct_client(self):
        """Test extracting IP from direct client connection."""
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "1.2.3.4"

        ip = get_client_ip(request)

        assert ip == "1.2.3.4"

    def test_no_ip_available(self):
        """Test when no IP is available."""
        request = MagicMock()
        request.headers = {}
        request.client = None

        ip = get_client_ip(request)

        assert ip is None


@pytest.mark.integration
@pytest.mark.asyncio
class TestCheckRateLimitDependency:
    """Integration tests for check_rate_limit dependency."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app with rate limit dependency."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(ip: str | None = Depends(check_rate_limit)):
            return {"ip": ip}

        return app

    async def test_request_with_x_forwarded_for(self, test_app):
        """Test request with X-Forwarded-For header."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get(
                "/test",
                headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"},
            )

            assert response.status_code == 200
            assert response.json()["ip"] == "1.2.3.4"

    async def test_request_with_x_real_ip(self, test_app):
        """Test request with X-Real-IP header."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get(
                "/test",
                headers={"X-Real-IP": "1.2.3.4"},
            )

            assert response.status_code == 200
            assert response.json()["ip"] == "1.2.3.4"

    async def test_blocked_ip_returns_429(self, test_app):
        """Test that blocked IP returns 429 Too Many Requests."""
        with patch("app.dependencies.rate_limit.RateLimitService.is_ip_blocked") as mock_blocked:
            # Mock the IP as blocked
            block_info = MagicMock()
            block_info.remaining_seconds = 300
            mock_blocked.return_value = (True, block_info)

            async with AsyncClient(app=test_app, base_url="http://test") as client:
                response = await client.get(
                    "/test",
                    headers={"X-Forwarded-For": "1.2.3.4"},
                )

                assert response.status_code == 429
                assert "Too many failed attempts" in response.json()["detail"]
                assert "Retry-After" in response.headers
                assert response.headers["Retry-After"] == "300"

    async def test_non_blocked_ip_succeeds(self, test_app):
        """Test that non-blocked IP succeeds."""
        with patch("app.dependencies.rate_limit.RateLimitService.is_ip_blocked") as mock_blocked:
            # Mock the IP as not blocked
            mock_blocked.return_value = (False, None)

            async with AsyncClient(app=test_app, base_url="http://test") as client:
                response = await client.get(
                    "/test",
                    headers={"X-Forwarded-For": "1.2.3.4"},
                )

                assert response.status_code == 200
                assert response.json()["ip"] == "1.2.3.4"


@pytest.mark.unit
class TestProxyScenarios:
    """Test realistic reverse proxy scenarios."""

    def test_cloudflare_proxy(self):
        """Test IP extraction in Cloudflare proxy scenario."""
        request = MagicMock()
        # Cloudflare sets both headers
        request.headers = {
            "x-forwarded-for": "203.0.113.1, 104.16.0.1",  # client, cloudflare
            "x-real-ip": "203.0.113.1",
        }
        request.client = MagicMock()
        request.client.host = "104.16.0.1"  # Cloudflare IP

        ip = get_client_ip(request)

        # Should get the actual client IP, not Cloudflare's
        assert ip == "203.0.113.1"

    def test_nginx_proxy(self):
        """Test IP extraction in Nginx proxy scenario."""
        request = MagicMock()
        # Nginx typically sets X-Real-IP
        request.headers = {"x-real-ip": "203.0.113.1"}
        request.client = MagicMock()
        request.client.host = "10.0.0.1"  # Internal proxy IP

        ip = get_client_ip(request)

        # Should get the actual client IP, not internal proxy IP
        assert ip == "203.0.113.1"

    def test_multiple_proxies(self):
        """Test IP extraction through multiple proxy layers."""
        request = MagicMock()
        # Request went through multiple proxies
        request.headers = {
            "x-forwarded-for": "203.0.113.1, 10.0.0.1, 10.0.0.2"
        }  # client, proxy1, proxy2
        request.client = MagicMock()
        request.client.host = "10.0.0.2"

        ip = get_client_ip(request)

        # Should always get the leftmost IP (original client)
        assert ip == "203.0.113.1"

    def test_direct_connection_no_proxy(self):
        """Test IP extraction for direct connection without proxy."""
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "203.0.113.1"

        ip = get_client_ip(request)

        assert ip == "203.0.113.1"
