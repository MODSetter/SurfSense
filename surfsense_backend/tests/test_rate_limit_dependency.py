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


@pytest.mark.unit
class TestIPv6Support:
    """Test cases for IPv6 address support."""

    def test_get_ipv6_from_direct_client(self):
        """Test extracting IPv6 address from direct client connection."""
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"

        ip = get_client_ip(request)

        assert ip == "2001:0db8:85a3:0000:0000:8a2e:0370:7334"

    def test_get_ipv6_from_x_forwarded_for(self):
        """Test extracting IPv6 from X-Forwarded-For header."""
        request = MagicMock()
        request.headers = {"x-forwarded-for": "2001:db8::1, 2001:db8::2"}
        request.client = None

        ip = get_client_ip(request)

        assert ip == "2001:db8::1"

    def test_get_ipv6_from_x_real_ip(self):
        """Test extracting IPv6 from X-Real-IP header."""
        request = MagicMock()
        request.headers = {"x-real-ip": "2001:db8::1"}
        request.client = None

        ip = get_client_ip(request)

        assert ip == "2001:db8::1"

    def test_compressed_ipv6(self):
        """Test compressed IPv6 notation (::)."""
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "::1"  # IPv6 loopback

        ip = get_client_ip(request)

        assert ip == "::1"

    def test_ipv6_with_port_stripped(self):
        """Test IPv6 address with port is properly handled."""
        # Note: FastAPI's request.client.host should already strip the port
        # This test ensures our validation handles IPv6 correctly
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "2001:db8::1"  # Port already stripped by FastAPI

        ip = get_client_ip(request)

        assert ip == "2001:db8::1"

    def test_invalid_ipv6(self):
        """Test invalid IPv6 address is rejected."""
        request = MagicMock()
        request.headers = {"x-forwarded-for": "not:a:valid:ipv6:address"}
        request.client = None

        ip = get_client_ip(request)

        # Should return None due to validation failure
        assert ip is None

    def test_mixed_ipv4_mapped_ipv6(self):
        """Test IPv4-mapped IPv6 address."""
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "::ffff:192.0.2.1"  # IPv4-mapped IPv6

        ip = get_client_ip(request)

        assert ip == "::ffff:192.0.2.1"

    def test_ipv6_in_proxy_chain(self):
        """Test IPv6 address through proxy chain."""
        request = MagicMock()
        request.headers = {
            "x-forwarded-for": "2001:db8::1, 2001:db8::proxy1, 2001:db8::proxy2"
        }
        request.client = MagicMock()
        request.client.host = "2001:db8::proxy2"

        ip = get_client_ip(request)

        # Should return the leftmost IPv6 (original client)
        assert ip == "2001:db8::1"


@pytest.mark.unit
class TestCloudflareIntegration:
    """Test cases for Cloudflare-specific functionality."""

    def test_cloudflare_ip_detection_ipv4(self):
        """Test detecting Cloudflare IPv4 addresses."""
        from app.dependencies.rate_limit import is_cloudflare_ip

        # Valid Cloudflare IPv4 (from 173.245.48.0/20 range)
        assert is_cloudflare_ip("173.245.48.1") is True
        assert is_cloudflare_ip("173.245.63.255") is True

        # Valid Cloudflare IPv4 (from 104.16.0.0/13 range)
        assert is_cloudflare_ip("104.16.0.1") is True
        assert is_cloudflare_ip("104.23.255.255") is True

        # Non-Cloudflare IP
        assert is_cloudflare_ip("8.8.8.8") is False
        assert is_cloudflare_ip("192.168.1.1") is False

    def test_cloudflare_ip_detection_ipv6(self):
        """Test detecting Cloudflare IPv6 addresses."""
        from app.dependencies.rate_limit import is_cloudflare_ip

        # Valid Cloudflare IPv6 (from 2606:4700::/32 range)
        assert is_cloudflare_ip("2606:4700::1") is True
        assert is_cloudflare_ip("2606:4700:ffff:ffff:ffff:ffff:ffff:ffff") is True

        # Valid Cloudflare IPv6 (from 2400:cb00::/32 range)
        assert is_cloudflare_ip("2400:cb00::1") is True

        # Non-Cloudflare IPv6
        assert is_cloudflare_ip("2001:db8::1") is False

    def test_cf_connecting_ip_header(self, monkeypatch):
        """Test CF-Connecting-IP header takes priority for Cloudflare requests."""
        # Set environment to use Cloudflare proxies
        monkeypatch.setenv("CLOUDFLARE_PROXIES", "true")

        # Reload module to pick up env var
        import importlib
        import app.dependencies.rate_limit
        importlib.reload(app.dependencies.rate_limit)
        from app.dependencies.rate_limit import get_client_ip

        request = MagicMock()
        request.headers = {
            "cf-connecting-ip": "203.0.113.1",
            "x-forwarded-for": "203.0.113.1, 173.245.48.1",
        }
        request.client = MagicMock()
        request.client.host = "173.245.48.1"  # Cloudflare IP

        ip = get_client_ip(request)

        # Should use CF-Connecting-IP since request is from Cloudflare
        assert ip == "203.0.113.1"

    def test_cf_connecting_ip_not_trusted_from_non_cloudflare(self, monkeypatch):
        """Test CF-Connecting-IP is ignored when request doesn't come from Cloudflare."""
        # Set environment to use Cloudflare proxies
        monkeypatch.setenv("CLOUDFLARE_PROXIES", "true")

        # Reload module
        import importlib
        import app.dependencies.rate_limit
        importlib.reload(app.dependencies.rate_limit)
        from app.dependencies.rate_limit import get_client_ip

        request = MagicMock()
        request.headers = {
            "cf-connecting-ip": "1.2.3.4",  # Fake CF header
            "x-forwarded-for": "5.6.7.8, 1.2.3.4",
        }
        request.client = MagicMock()
        request.client.host = "10.0.0.1"  # NOT a Cloudflare IP

        ip = get_client_ip(request)

        # Should NOT use CF-Connecting-IP (not from Cloudflare)
        # Should fall back to direct client
        assert ip == "10.0.0.1"

    def test_get_cloudflare_metadata(self):
        """Test extracting Cloudflare metadata from headers."""
        from app.dependencies.rate_limit import get_cloudflare_metadata

        request = MagicMock()
        request.headers = {
            "cf-ray": "1234567890abc-SJC",
            "cf-ipcountry": "US",
            "cf-visitor": '{"scheme":"https"}',
            "cf-request-id": "req-12345",
        }

        metadata = get_cloudflare_metadata(request)

        assert metadata["cf_ray"] == "1234567890abc-SJC"
        assert metadata["cf_country"] == "US"
        assert metadata["cf_visitor"] == '{"scheme":"https"}'
        assert metadata["cf_request_id"] == "req-12345"

    def test_get_cloudflare_metadata_partial(self):
        """Test extracting partial Cloudflare metadata."""
        from app.dependencies.rate_limit import get_cloudflare_metadata

        request = MagicMock()
        request.headers = {
            "cf-ray": "1234567890abc-SJC",
            # Only CF-Ray present
        }

        metadata = get_cloudflare_metadata(request)

        assert metadata["cf_ray"] == "1234567890abc-SJC"
        assert "cf_country" not in metadata
        assert "cf_visitor" not in metadata

    def test_get_cloudflare_metadata_none(self):
        """Test with no Cloudflare headers."""
        from app.dependencies.rate_limit import get_cloudflare_metadata

        request = MagicMock()
        request.headers = {}

        metadata = get_cloudflare_metadata(request)

        assert metadata == {}

    def test_invalid_ip_in_cf_connecting_ip(self, monkeypatch):
        """Test invalid IP in CF-Connecting-IP is rejected."""
        monkeypatch.setenv("CLOUDFLARE_PROXIES", "true")

        import importlib
        import app.dependencies.rate_limit
        importlib.reload(app.dependencies.rate_limit)
        from app.dependencies.rate_limit import get_client_ip

        request = MagicMock()
        request.headers = {
            "cf-connecting-ip": "not-an-ip",
            "x-forwarded-for": "203.0.113.1",
        }
        request.client = MagicMock()
        request.client.host = "173.245.48.1"  # Cloudflare IP

        ip = get_client_ip(request)

        # Should fall back to X-Forwarded-For due to invalid CF-Connecting-IP
        assert ip == "203.0.113.1"


@pytest.mark.unit
class TestTrustedProxies:
    """Test cases for TRUSTED_PROXIES functionality with CIDR support."""

    def test_parse_single_ip(self, monkeypatch):
        """Test parsing single IP address."""
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")

        import importlib
        import app.dependencies.rate_limit
        importlib.reload(app.dependencies.rate_limit)
        from app.dependencies.rate_limit import TRUSTED_PROXY_NETWORKS

        assert len(TRUSTED_PROXY_NETWORKS) == 1
        assert str(TRUSTED_PROXY_NETWORKS[0]) == "10.0.0.1/32"

    def test_parse_cidr_range(self, monkeypatch):
        """Test parsing CIDR range."""
        monkeypatch.setenv("TRUSTED_PROXIES", "192.168.1.0/24")

        import importlib
        import app.dependencies.rate_limit
        importlib.reload(app.dependencies.rate_limit)
        from app.dependencies.rate_limit import TRUSTED_PROXY_NETWORKS

        assert len(TRUSTED_PROXY_NETWORKS) == 1
        assert str(TRUSTED_PROXY_NETWORKS[0]) == "192.168.1.0/24"

    def test_parse_multiple_mixed(self, monkeypatch):
        """Test parsing multiple IPs and CIDR ranges."""
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1,192.168.1.0/24,172.16.0.0/16")

        import importlib
        import app.dependencies.rate_limit
        importlib.reload(app.dependencies.rate_limit)
        from app.dependencies.rate_limit import TRUSTED_PROXY_NETWORKS

        assert len(TRUSTED_PROXY_NETWORKS) == 3

    def test_parse_invalid_ip(self, monkeypatch):
        """Test that invalid IPs are skipped with warning."""
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1,invalid-ip,192.168.1.0/24")

        import importlib
        import app.dependencies.rate_limit
        importlib.reload(app.dependencies.rate_limit)
        from app.dependencies.rate_limit import TRUSTED_PROXY_NETWORKS

        # Should have 2 valid networks, invalid one skipped
        assert len(TRUSTED_PROXY_NETWORKS) == 2

    def test_is_trusted_proxy_single_ip(self, monkeypatch):
        """Test is_trusted_proxy with single IP."""
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")

        import importlib
        import app.dependencies.rate_limit
        importlib.reload(app.dependencies.rate_limit)
        from app.dependencies.rate_limit import is_trusted_proxy

        assert is_trusted_proxy("10.0.0.1") is True
        assert is_trusted_proxy("10.0.0.2") is False

    def test_is_trusted_proxy_cidr_range(self, monkeypatch):
        """Test is_trusted_proxy with CIDR range."""
        monkeypatch.setenv("TRUSTED_PROXIES", "192.168.1.0/24")

        import importlib
        import app.dependencies.rate_limit
        importlib.reload(app.dependencies.rate_limit)
        from app.dependencies.rate_limit import is_trusted_proxy

        assert is_trusted_proxy("192.168.1.1") is True
        assert is_trusted_proxy("192.168.1.255") is True
        assert is_trusted_proxy("192.168.2.1") is False
        assert is_trusted_proxy("10.0.0.1") is False

    def test_get_client_ip_from_trusted_proxy(self, monkeypatch):
        """Test get_client_ip trusts headers from trusted proxy."""
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")

        import importlib
        import app.dependencies.rate_limit
        importlib.reload(app.dependencies.rate_limit)
        from app.dependencies.rate_limit import get_client_ip

        request = MagicMock()
        request.headers = {"x-forwarded-for": "203.0.113.1, 10.0.0.1"}
        request.client = MagicMock()
        request.client.host = "10.0.0.1"  # Trusted proxy

        ip = get_client_ip(request)

        # Should trust X-Forwarded-For from trusted proxy
        assert ip == "203.0.113.1"

    def test_get_client_ip_from_untrusted_proxy(self, monkeypatch):
        """Test get_client_ip ignores headers from untrusted proxy."""
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")

        import importlib
        import app.dependencies.rate_limit
        importlib.reload(app.dependencies.rate_limit)
        from app.dependencies.rate_limit import get_client_ip

        request = MagicMock()
        request.headers = {"x-forwarded-for": "203.0.113.1, 10.0.0.2"}
        request.client = MagicMock()
        request.client.host = "10.0.0.2"  # NOT trusted proxy

        ip = get_client_ip(request)

        # Should use direct client IP, not trust X-Forwarded-For
        assert ip == "10.0.0.2"

    def test_get_client_ip_from_cidr_trusted_proxy(self, monkeypatch):
        """Test get_client_ip with proxy in trusted CIDR range."""
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.0/24")

        import importlib
        import app.dependencies.rate_limit
        importlib.reload(app.dependencies.rate_limit)
        from app.dependencies.rate_limit import get_client_ip

        request = MagicMock()
        request.headers = {"x-forwarded-for": "203.0.113.1"}
        request.client = MagicMock()
        request.client.host = "10.0.0.50"  # Within trusted CIDR range

        ip = get_client_ip(request)

        # Should trust X-Forwarded-For from proxy in trusted range
        assert ip == "203.0.113.1"

    def test_empty_trusted_proxies(self, monkeypatch):
        """Test behavior when TRUSTED_PROXIES is empty."""
        monkeypatch.setenv("TRUSTED_PROXIES", "")

        import importlib
        import app.dependencies.rate_limit
        importlib.reload(app.dependencies.rate_limit)
        from app.dependencies.rate_limit import TRUSTED_PROXY_NETWORKS, is_trusted_proxy

        assert len(TRUSTED_PROXY_NETWORKS) == 0
        assert is_trusted_proxy("10.0.0.1") is False
