# Security Improvements Documentation

This document details the comprehensive security enhancements implemented in the SurfSense backend to protect against common web vulnerabilities and attacks.

## Table of Contents

1. [Overview](#overview)
2. [IP Address Validation](#ip-address-validation)
3. [Trusted Proxy Configuration](#trusted-proxy-configuration)
4. [Rate Limiting Enhancements](#rate-limiting-enhancements)
5. [Comprehensive Security Logging](#comprehensive-security-logging)
6. [Content Security Policy (CSP)](#content-security-policy-csp)
7. [IPv6 Support](#ipv6-support)
8. [Configuration Guide](#configuration-guide)
9. [Monitoring and Alerting](#monitoring-and-alerting)
10. [Security Best Practices](#security-best-practices)

---

## Overview

The security improvements focus on defense in depth, implementing multiple layers of protection:

- **IP Address Validation**: Prevents malformed IP data from bypassing rate limiting
- **Trusted Proxy List**: Prevents IP spoofing attacks via forged headers
- **Enhanced Rate Limiting**: Protects login and 2FA endpoints from brute force
- **Comprehensive Logging**: Structured security event logging for monitoring and forensics
- **Improved CSP**: Maintainable Content Security Policy configuration
- **IPv6 Support**: Full support for IPv6 addresses in rate limiting and logging
- **Timing Attack Prevention**: Generic error messages and rounded retry times

---

## IP Address Validation

### Implementation

Located in: `app/dependencies/rate_limit.py`

The `is_valid_ip()` function validates all IP addresses before using them for rate limiting:

```python
def is_valid_ip(ip_str: str) -> bool:
    """
    Validate if a string is a valid IP address.

    Returns:
        True if valid IPv4 or IPv6 address, False otherwise
    """
    if not ip_str:
        return False

    try:
        ipaddress.ip_address(ip_str.strip())
        return True
    except ValueError:
        return False
```

### Benefits

- **Prevents Bypass**: Malformed IPs cannot be used to circumvent rate limiting
- **Input Sanitization**: Ensures only valid IPs are stored in Redis and database
- **Security Logging**: Invalid IPs are logged with warnings for security monitoring

### Examples

```python
# Valid IPs
is_valid_ip("192.168.1.1")                                    # ✓ True (IPv4)
is_valid_ip("2001:db8::1")                                    # ✓ True (IPv6)
is_valid_ip("::1")                                            # ✓ True (IPv6 loopback)

# Invalid IPs
is_valid_ip("999.999.999.999")                                # ✗ False
is_valid_ip("not-an-ip")                                      # ✗ False
is_valid_ip("<script>alert('xss')</script>")                  # ✗ False
```

---

## Trusted Proxy Configuration

### The Problem

Attackers can forge HTTP headers like `X-Forwarded-For` to:
- Bypass IP-based rate limiting by rotating fake IPs
- Frame other users by using their IP addresses
- Evade blocking by constantly changing their apparent IP

### The Solution

Only trust proxy headers when the immediate client is a known, trusted proxy.

### Configuration

Set the `TRUSTED_PROXIES` environment variable with comma-separated proxy IPs:

```bash
# Production example
TRUSTED_PROXIES=10.0.0.1,10.0.0.2,172.16.0.1

# Cloudflare example (use Cloudflare IP ranges)
TRUSTED_PROXIES=173.245.48.0/20,103.21.244.0/22

# Nginx reverse proxy example
TRUSTED_PROXIES=10.0.0.5
```

### Implementation Details

Located in: `app/dependencies/rate_limit.py`

```python
# Load trusted proxies from environment
TRUSTED_PROXIES = set(
    filter(None, os.getenv("TRUSTED_PROXIES", "").split(","))
)

def get_client_ip(request: Request) -> str | None:
    """Extract real client IP with trusted proxy validation."""
    immediate_client = request.client.host if request.client else None

    # Only trust proxy headers if immediate client is in trusted list
    trust_proxy_headers = False
    if TRUSTED_PROXIES and immediate_client:
        trust_proxy_headers = immediate_client in TRUSTED_PROXIES
    elif not TRUSTED_PROXIES:
        # Backward compatible: trust all if not configured
        trust_proxy_headers = True

    # Check proxy headers only if trusted...
```

### Deployment Scenarios

#### Scenario 1: Direct Internet Connection
```bash
# No proxies - leave unset or empty
TRUSTED_PROXIES=
```

#### Scenario 2: Behind Nginx Reverse Proxy
```bash
# Trust your Nginx server
TRUSTED_PROXIES=10.0.0.1

# Nginx configuration
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
```

#### Scenario 3: Behind Cloudflare
```bash
# Trust Cloudflare IP ranges (use current Cloudflare IPs)
TRUSTED_PROXIES=173.245.48.0/20,103.21.244.0/22,188.114.96.0/20

# Cloudflare automatically sets:
# - CF-Connecting-IP (recommended)
# - X-Forwarded-For
```

#### Scenario 4: Multiple Proxy Layers
```bash
# Trust both your load balancer and CDN
TRUSTED_PROXIES=10.0.0.1,10.0.0.2,172.16.0.1
```

### Security Implications

⚠️ **Warning**: If you're behind a reverse proxy and don't set `TRUSTED_PROXIES`:
- All requests will appear to come from the proxy IP
- Rate limiting will affect ALL users instead of individual attackers
- This makes rate limiting ineffective!

✅ **Best Practice**: Always configure `TRUSTED_PROXIES` in production when behind a proxy.

---

## Rate Limiting Enhancements

### Endpoints Protected

All authentication-related endpoints are now protected:

1. **Login Endpoint** (`/2fa/login`)
   - Protects against password brute force attacks
   - Tracks failed login attempts per IP
   - Blocks after 5 failed attempts (configurable)

2. **2FA Setup Verification** (`/2fa/verify-setup`)
   - Prevents brute force of 2FA codes during setup
   - Rate limits TOTP code guessing attempts

3. **2FA Login Verification** (`/2fa/verify`)
   - Protects against 2FA code brute force
   - Prevents bypass of 2FA protection

### Configuration

Rate limiting behavior is controlled by environment variables:

```bash
# Maximum failed attempts before blocking (default: 5)
RATE_LIMIT_MAX_ATTEMPTS=5

# How long to block IP after exceeding limit (default: 60 minutes)
RATE_LIMIT_LOCKOUT_MINUTES=60

# Time window for counting attempts (default: 15 minutes)
RATE_LIMIT_WINDOW_MINUTES=15
```

### Implementation

Rate limiting uses a reusable FastAPI dependency:

```python
from app.dependencies import check_rate_limit

@router.post("/login")
async def login(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    ip_address: str | None = Depends(check_rate_limit),  # ✅ Add this
):
    # IP is automatically checked, 429 raised if blocked
    # If we get here, rate limit passed
    ...
```

### Timing Attack Prevention

Error messages and timing are intentionally obfuscated:

```python
# ✗ BAD: Reveals exact timing
detail="Try again in 1847 seconds"

# ✅ GOOD: Rounds to nearest minute
remaining_minutes = max(1, (remaining_seconds + 30) // 60)
detail="Too many failed attempts. Please try again later."
headers={"Retry-After": str(remaining_minutes * 60)}
```

This prevents attackers from:
- Using precise timing to optimize brute force attacks
- Determining the exact rate limit window
- Inferring information about other users' activities

---

## Comprehensive Security Logging

### Event Types

New security event types added to `SecurityEventType` enum:

```python
class SecurityEventType(str, Enum):
    # Existing events
    PASSWORD_LOGIN_FAILED = "PASSWORD_LOGIN_FAILED"
    TWO_FA_LOGIN_FAILED = "TWO_FA_LOGIN_FAILED"
    RATE_LIMIT_AUTO_BLOCK = "RATE_LIMIT_AUTO_BLOCK"

    # New events
    RATE_LIMIT_HIT = "RATE_LIMIT_HIT"                     # Blocked IP tries to access
    RATE_LIMIT_ATTEMPT_RECORDED = "RATE_LIMIT_ATTEMPT_RECORDED"  # Failed attempt logged
```

### What Gets Logged

#### 1. Failed Attempts (Before Blocking)

Logged when a failed attempt is recorded but IP is not yet blocked:

```json
{
  "event_type": "RATE_LIMIT_ATTEMPT_RECORDED",
  "user_id": "uuid-here",
  "ip_address": "1.2.3.4",
  "success": false,
  "details": {
    "attempt_count": 3,
    "reason": "failed_password_login",
    "endpoint": "/2fa/login"
  },
  "created_at": "2025-01-15T10:30:00Z"
}
```

#### 2. Rate Limit Hits (Blocked Access)

Logged when a blocked IP tries to access a protected endpoint:

```json
{
  "event_type": "RATE_LIMIT_HIT",
  "user_id": "uuid-here",
  "ip_address": "1.2.3.4",
  "success": false,
  "details": {
    "endpoint": "/2fa/verify",
    "remaining_seconds": 2400,
    "failed_attempts": 5,
    "reason": "exceeded_max_attempts",
    "lockout_type": "temporary"
  },
  "created_at": "2025-01-15T10:31:00Z"
}
```

#### 3. Python Logger (Structured)

All rate limiting events also log to Python logger with structured data:

```python
# Failed attempt recorded
logger.info(
    f"Failed attempt recorded: IP {ip_address}, "
    f"attempts: {attempts}/{MAX_FAILED_ATTEMPTS}, "
    f"user: {username}, "
    f"reason: {reason}"
)

# Rate limit hit (blocked access)
logger.warning(
    f"Rate limit hit: IP {ip_address} blocked from accessing {endpoint}. "
    f"Attempts: {failed_attempts}, "
    f"Remaining: {remaining_seconds}s, "
    f"Reason: {reason}"
)
```

### Querying Security Events

#### Find All Failed Login Attempts for IP

```sql
SELECT *
FROM security_events
WHERE ip_address = '1.2.3.4'
  AND event_type IN ('PASSWORD_LOGIN_FAILED', 'TWO_FA_LOGIN_FAILED')
ORDER BY created_at DESC
LIMIT 100;
```

#### Identify Attack Patterns

```sql
-- Find IPs with multiple failed attempts across different endpoints
SELECT
    ip_address,
    COUNT(*) as total_attempts,
    COUNT(DISTINCT details->>'endpoint') as endpoints_targeted,
    MIN(created_at) as first_attempt,
    MAX(created_at) as last_attempt
FROM security_events
WHERE event_type = 'RATE_LIMIT_ATTEMPT_RECORDED'
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY ip_address
HAVING COUNT(*) >= 10
ORDER BY total_attempts DESC;
```

#### Monitor Rate Limit Effectiveness

```sql
-- Count blocks vs attempts per hour
SELECT
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) FILTER (WHERE event_type = 'RATE_LIMIT_ATTEMPT_RECORDED') as attempts,
    COUNT(*) FILTER (WHERE event_type = 'RATE_LIMIT_AUTO_BLOCK') as blocks,
    COUNT(*) FILTER (WHERE event_type = 'RATE_LIMIT_HIT') as blocked_accesses
FROM security_events
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;
```

---

## Content Security Policy (CSP)

### Improvements

CSP configuration refactored from string-based to dictionary-based for maintainability.

#### Before (Hard to Maintain)
```python
csp = "default-src 'self'; script-src 'self' 'unsafe-inline'; ..."
```

#### After (Easy to Maintain)
```python
csp_directives = {
    "default-src": ["'self'"],
    "script-src": ["'self'", "'unsafe-inline'"],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:", "https:"],
    "font-src": ["'self'"],
    "connect-src": ["'self'"],
    "frame-ancestors": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "object-src": ["'none'"],
}
```

### Environment-Specific CSP

#### Production (Strict)
```python
if is_production:
    csp_directives = {
        "default-src": ["'self'"],
        "script-src": ["'self'"],  # No inline scripts
        "upgrade-insecure-requests": [],  # Force HTTPS
        ...
    }
```

#### Development (Permissive)
```python
else:
    csp_directives = {
        "default-src": ["'self'"],
        "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],  # Dev tools
        "connect-src": ["'self'", "ws://localhost:*"],  # Hot reload
        ...
    }
```

### Customizing CSP

You can customize CSP when adding the middleware:

```python
from app.middleware.security_headers import SecurityHeadersMiddleware

app.add_middleware(
    SecurityHeadersMiddleware,
    enable_hsts=True,
    enable_csp=True,
    csp_policy="default-src 'self'; img-src 'self' https://cdn.example.com",
)
```

---

## IPv6 Support

### Full IPv6 Compatibility

All IP validation, rate limiting, and logging now supports IPv6 addresses:

#### Supported IPv6 Formats

```python
# Full notation
"2001:0db8:85a3:0000:0000:8a2e:0370:7334"

# Compressed notation
"2001:db8:85a3::8a2e:370:7334"
"2001:db8::1"

# Loopback
"::1"

# IPv4-mapped IPv6
"::ffff:192.0.2.1"
```

### Database Schema

The `security_events` table IP address column supports up to 45 characters to accommodate full IPv6 addresses:

```sql
CREATE TABLE security_events (
    ...
    ip_address VARCHAR(45),  -- IPv6 max length is 45
    ...
);
```

### Testing

Comprehensive IPv6 tests added in `tests/test_rate_limit_dependency.py`:

```python
def test_get_ipv6_from_x_forwarded_for():
    """Test extracting IPv6 from X-Forwarded-For header."""
    request = MagicMock()
    request.headers = {"x-forwarded-for": "2001:db8::1, 2001:db8::2"}

    ip = get_client_ip(request)

    assert ip == "2001:db8::1"
```

---

## Configuration Guide

### Environment Variables

#### Rate Limiting
```bash
# Redis connection (shared with Celery)
CELERY_BROKER_URL=redis://localhost:6379/0

# Rate limiting configuration
RATE_LIMIT_MAX_ATTEMPTS=5          # Failed attempts before block
RATE_LIMIT_LOCKOUT_MINUTES=60      # Block duration (minutes)
RATE_LIMIT_WINDOW_MINUTES=15       # Attempt counting window
```

#### Trusted Proxies
```bash
# Comma-separated list of trusted proxy IPs
TRUSTED_PROXIES=10.0.0.1,172.16.0.1

# Or leave empty if not behind a proxy
TRUSTED_PROXIES=
```

#### Security Headers
```bash
# Set environment (affects CSP and HSTS)
ENVIRONMENT=production  # or 'development'
```

### Docker Compose Example

```yaml
services:
  backend:
    environment:
      # Rate limiting
      - RATE_LIMIT_MAX_ATTEMPTS=5
      - RATE_LIMIT_LOCKOUT_MINUTES=60
      - RATE_LIMIT_WINDOW_MINUTES=15

      # Trusted proxies (Nginx container)
      - TRUSTED_PROXIES=172.18.0.3

      # Environment
      - ENVIRONMENT=production

      # Redis
      - CELERY_BROKER_URL=redis://redis:6379/0
```

### Kubernetes Example

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: backend-config
data:
  RATE_LIMIT_MAX_ATTEMPTS: "5"
  RATE_LIMIT_LOCKOUT_MINUTES: "60"
  RATE_LIMIT_WINDOW_MINUTES: "15"
  ENVIRONMENT: "production"
  # Cloudflare IPs as trusted proxies
  TRUSTED_PROXIES: "173.245.48.0/20,103.21.244.0/22"
```

---

## Monitoring and Alerting

### Metrics to Monitor

#### 1. Failed Login Attempts
```python
# Query: Count of failed login attempts per hour
SELECT
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as failed_attempts
FROM security_events
WHERE event_type IN ('PASSWORD_LOGIN_FAILED', 'TWO_FA_LOGIN_FAILED')
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;
```

**Alert Threshold**: > 100 failed attempts per hour

#### 2. Rate Limit Blocks
```python
# Query: IPs blocked by rate limiting
SELECT
    ip_address,
    COUNT(*) as block_count,
    MAX(created_at) as last_block
FROM security_events
WHERE event_type = 'RATE_LIMIT_AUTO_BLOCK'
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY ip_address
ORDER BY block_count DESC;
```

**Alert Threshold**: > 50 unique IPs blocked per day (possible DDoS)

#### 3. Persistent Attackers
```python
# Query: IPs that keep trying after being blocked
SELECT
    ip_address,
    COUNT(*) as hit_count,
    MAX(created_at) as last_hit
FROM security_events
WHERE event_type = 'RATE_LIMIT_HIT'
  AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY ip_address
HAVING COUNT(*) > 10
ORDER BY hit_count DESC;
```

**Alert Threshold**: > 50 hits from single IP per hour (add to permanent block list)

### Log Aggregation

#### Structured Logging Format

All security events use structured logging for easy parsing:

```python
logger.warning(
    f"Rate limit hit: IP {ip_address} blocked from accessing {endpoint}",
    extra={
        "ip_address": ip_address,
        "endpoint": endpoint,
        "attempts": failed_attempts,
        "remaining_seconds": remaining_seconds,
        "event_type": "rate_limit_hit"
    }
)
```

#### Example: Splunk Query

```splunk
index=surfsense sourcetype=python
| search event_type="rate_limit_hit"
| stats count by ip_address, endpoint
| where count > 10
| sort - count
```

#### Example: ELK Stack Query

```json
GET /logs/_search
{
  "query": {
    "bool": {
      "must": [
        { "term": { "event_type": "rate_limit_hit" } },
        { "range": { "@timestamp": { "gte": "now-1h" } } }
      ]
    }
  },
  "aggs": {
    "by_ip": {
      "terms": { "field": "ip_address.keyword", "size": 50 }
    }
  }
}
```

### Grafana Dashboard

Example Prometheus metrics:

```python
# Failed login attempts counter
rate_limit_failed_attempts_total{reason="failed_password_login"}

# Blocked IPs gauge
rate_limit_blocked_ips_current

# Rate limit hits counter
rate_limit_hits_total{endpoint="/2fa/login"}
```

---

## Security Best Practices

### 1. Regular Security Audits

- Review security events weekly
- Analyze attack patterns and trends
- Update rate limits based on observed behavior
- Investigate unusual patterns immediately

### 2. Incident Response

When detecting an attack:

1. **Identify the scope**: How many IPs? Which endpoints?
2. **Block at network level**: Add persistent blocks to firewall
3. **Analyze logs**: Look for patterns, compromised accounts
4. **Update defenses**: Adjust rate limits if needed
5. **Document**: Record incident details for future reference

### 3. Configuration Hardening

#### Production Checklist

- [ ] Set `ENVIRONMENT=production`
- [ ] Configure `TRUSTED_PROXIES` (if behind proxy)
- [ ] Enable HSTS with long max-age
- [ ] Use strict CSP (no `unsafe-inline` or `unsafe-eval`)
- [ ] Set strong rate limits
- [ ] Enable comprehensive logging
- [ ] Set up monitoring and alerting
- [ ] Regular security event reviews

#### Development Best Practices

- [ ] Use separate Redis instance for dev
- [ ] Don't use production secrets in dev
- [ ] Test rate limiting with real scenarios
- [ ] Validate IPv6 support in your environment
- [ ] Review security events in dev for anomalies

### 4. Defense in Depth

Rate limiting is ONE layer of security. Also implement:

- **Strong password policies**: Enforce complexity requirements
- **2FA**: Require 2FA for sensitive accounts
- **Account lockout**: Permanent block after excessive failures
- **CAPTCHA**: Add CAPTCHA after several failed attempts
- **Geo-blocking**: Block countries where you don't operate
- **WAF**: Web Application Firewall for additional protection

### 5. Keep Dependencies Updated

Regularly update security-related dependencies:

```bash
# Check for security vulnerabilities
uv run safety check

# Update dependencies
uv sync --upgrade
```

---

## Troubleshooting

### Issue: All users appear to come from same IP

**Cause**: Behind reverse proxy but `TRUSTED_PROXIES` not set

**Solution**:
```bash
# Find your proxy IP
docker network inspect <network> | grep Gateway

# Set TRUSTED_PROXIES
export TRUSTED_PROXIES=172.18.0.1
```

### Issue: Rate limiting not working

**Cause**: Redis connection issue

**Solution**:
```bash
# Check Redis is running
redis-cli ping

# Check connection from backend
export CELERY_BROKER_URL=redis://localhost:6379/0
python -c "import redis; r = redis.from_url('redis://localhost:6379/0'); print(r.ping())"
```

### Issue: False positives (legitimate users blocked)

**Cause**: Rate limits too aggressive

**Solution**:
```bash
# Increase limits
export RATE_LIMIT_MAX_ATTEMPTS=10
export RATE_LIMIT_LOCKOUT_MINUTES=30

# Or manually unlock IP
curl -X POST http://localhost:8000/admin/rate-limit/unlock \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"ip_address": "1.2.3.4"}'
```

### Issue: Logs not appearing in database

**Cause**: Database session not committed or error in logging

**Solution**: Check logs for exceptions during security event logging. Logging failures should not break the application but will be logged to Python logger.

---

## Cloudflare Integration

### Overview

SurfSense includes comprehensive Cloudflare integration for enhanced security, performance, and global CDN delivery. When deployed behind Cloudflare, the application automatically detects and handles Cloudflare-specific headers for accurate IP detection and enhanced logging.

### Quick Setup

Enable Cloudflare integration with a single environment variable:

```bash
CLOUDFLARE_PROXIES=true
```

This automatically:
- ✅ Trusts Cloudflare's IP ranges (300+ edge locations)
- ✅ Uses `CF-Connecting-IP` header for real client IPs
- ✅ Logs Cloudflare metadata (CF-Ray, CF-IPCountry, CF-Visitor, etc.)
- ✅ Prevents IP spoofing (only trusts headers from Cloudflare IPs)

### Cloudflare Headers Supported

#### CF-Connecting-IP
The most reliable header for determining the real client IP when behind Cloudflare. This header cannot be spoofed because it's only trusted when the immediate client IP is from Cloudflare's network.

```python
# Automatically used when CLOUDFLARE_PROXIES=true
# Priority: CF-Connecting-IP > X-Forwarded-For > X-Real-IP > Direct Client
```

#### CF-Ray
Unique request identifier for correlating logs across Cloudflare's network and your backend.

**Example logged in security_events:**
```json
{
  "event_type": "RATE_LIMIT_HIT",
  "details": {
    "cloudflare": {
      "cf_ray": "8a1b2c3d4e5f-SJC",
      "cf_country": "US"
    }
  }
}
```

**Use Case:** Support requests
```
User: "I got an error at 2:30 PM"
You: "What's the CF-Ray ID from the error page?"
User: "8a1b2c3d4e5f-SJC"
You: *Searches logs for that CF-Ray* "Found it! The issue was..."
```

#### CF-IPCountry
ISO 3166-1 Alpha 2 country code of the client IP.

**Use Cases:**
- Geo-blocking for compliance (GDPR, sanctions, etc.)
- Attack pattern analysis (identify coordinated attacks from specific regions)
- Analytics and reporting

**Example: Logging by Country**
```sql
-- Top countries with failed login attempts
SELECT
    details->>'cloudflare'->>'cf_country' as country,
    COUNT(*) as failed_attempts
FROM security_events
WHERE event_type = 'PASSWORD_LOGIN_FAILED'
  AND details->>'cloudflare'->>'cf_country' IS NOT NULL
GROUP BY country
ORDER BY failed_attempts DESC
LIMIT 10;
```

#### CF-Visitor
JSON object indicating whether the original request was HTTP or HTTPS before reaching Cloudflare.

**Use Case:** Enforce HTTPS-only policies
```python
import json

cf_visitor = request.headers.get("cf-visitor")
if cf_visitor:
    visitor_data = json.loads(cf_visitor)
    if visitor_data.get("scheme") == "http":
        # Log security event - someone accessed via HTTP
        logger.warning(f"HTTP access attempt to {endpoint}")
```

### Cloudflare IP Ranges

The application includes Cloudflare's current IP ranges (as of January 2025):

**IPv4 Ranges:**
- 173.245.48.0/20, 103.21.244.0/22, 103.22.200.0/22
- 103.31.4.0/22, 141.101.64.0/18, 108.162.192.0/18
- And 9 more ranges...

**IPv6 Ranges:**
- 2400:cb00::/32, 2606:4700::/32, 2803:f800::/32
- And 4 more ranges...

These ranges are automatically checked using the `is_cloudflare_ip()` function.

### Benefits of Cloudflare Integration

1. **Accurate Rate Limiting**: Individual user tracking instead of treating all users as a single Cloudflare IP
2. **Enhanced Logging**: CF-Ray and CF-IPCountry for better security monitoring
3. **Attack Attribution**: Identify attack patterns by country and trace requests end-to-end
4. **Support Debugging**: Cloudflare support can investigate issues using CF-Ray ID
5. **Geo-Intelligence**: Make security decisions based on geographic origin

### Configuration Examples

#### Production (Behind Cloudflare)
```bash
# Enable Cloudflare mode
CLOUDFLARE_PROXIES=true

# Rate limiting still applies per-user
RATE_LIMIT_MAX_ATTEMPTS=5
RATE_LIMIT_LOCKOUT_MINUTES=60
```

#### Production (Behind Nginx, not Cloudflare)
```bash
# Don't use Cloudflare mode
CLOUDFLARE_PROXIES=false

# Trust your Nginx proxy
TRUSTED_PROXIES=10.0.0.1,10.0.0.2
```

#### Development (Direct Connection)
```bash
# No proxies
# (Leave unset or explicitly disable)
```

### Health Checks

The `/health` endpoints bypass rate limiting and are designed for Cloudflare Health Checks and load balancers:

- `/health` - Basic liveness check (no dependencies)
- `/health/ready` - Readiness check (verifies database, Redis)
- `/health/live` - Kubernetes liveness probe

**Cloudflare Load Balancer Configuration:**
```yaml
Health Check Settings:
  - Path: /health/ready
  - Expected Code: 200
  - Method: GET
  - Interval: 60 seconds
  - Timeout: 5 seconds
  - Retries: 2
```

### Security Logging with Cloudflare

All security events include Cloudflare metadata when available:

```python
# Example security_events table entry
{
  "event_type": "RATE_LIMIT_HIT",
  "ip_address": "203.0.113.1",
  "user_agent": "Mozilla/5.0 ...",
  "details": {
    "endpoint": "/2fa/login",
    "failed_attempts": 5,
    "cloudflare": {
      "cf_ray": "8a1b2c3d4e5f-SJC",
      "cf_country": "US",
      "cf_visitor": "{\"scheme\":\"https\"}"
    }
  }
}
```

### Monitoring Queries

#### Find Attacks by Country
```sql
SELECT
    details->>'cloudflare'->>'cf_country' as country,
    COUNT(*) as attack_count,
    array_agg(DISTINCT ip_address) as attacker_ips
FROM security_events
WHERE event_type = 'RATE_LIMIT_AUTO_BLOCK'
  AND created_at > NOW() - INTERVAL '24 hours'
  AND details->>'cloudflare'->>'cf_country' IS NOT NULL
GROUP BY country
ORDER BY attack_count DESC;
```

#### Trace Request by CF-Ray
```sql
SELECT *
FROM security_events
WHERE details->>'cloudflare'->>'cf_ray' = '8a1b2c3d4e5f-SJC'
ORDER BY created_at;
```

#### HTTP vs HTTPS Access Patterns
```sql
SELECT
    details->>'cloudflare'->>'cf_visitor' as protocol,
    COUNT(*) as count
FROM security_events
WHERE details->>'cloudflare'->>'cf_visitor' IS NOT NULL
GROUP BY protocol;
```

### Complete Setup Guide

For complete Cloudflare configuration including:
- SSL/TLS settings
- WAF rules
- Edge rate limiting
- Bot management
- Performance optimization
- Monitoring and analytics
- Troubleshooting

**See: [CLOUDFLARE_SETUP.md](./CLOUDFLARE_SETUP.md)**

This comprehensive guide covers all aspects of deploying SurfSense behind Cloudflare, from basic setup to advanced features like Turnstile, Workers, and Waiting Rooms.

---

## References

- [OWASP Rate Limiting Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html)
- [OWASP Content Security Policy](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)
- [MDN Web Security](https://developer.mozilla.org/en-US/docs/Web/Security)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

---

## Changelog

### 2025-01-21
- Added IP address validation using `ipaddress` module
- Implemented trusted proxy list configuration
- Enhanced rate limiting on login endpoints
- Added comprehensive security event logging (database + Python logger)
- Refactored CSP to dictionary-based configuration
- Added full IPv6 support with comprehensive tests
- Implemented timing attack prevention
- Created comprehensive security documentation
- **Cloudflare Integration**:
  - Added automatic Cloudflare IP range detection
  - Implemented CF-Connecting-IP header support
  - Added CF-Ray logging for request correlation
  - Added CF-IPCountry logging for geo-tracking
  - Created health check endpoints (bypassing rate limiting)
  - Created comprehensive Cloudflare setup guide (CLOUDFLARE_SETUP.md)
  - Added Cloudflare-specific tests

---

## Contact

For security issues or questions:
- Open a security issue on GitHub (for non-critical issues)
- Email security@surfsense.ai (for critical vulnerabilities)
- Review security events regularly via admin dashboard
