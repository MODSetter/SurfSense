# Cloudflare Setup Guide for SurfSense

This comprehensive guide covers setting up and configuring Cloudflare for optimal security, performance, and reliability with the SurfSense backend.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Backend Configuration](#backend-configuration)
4. [Cloudflare Dashboard Settings](#cloudflare-dashboard-settings)
5. [Security Configuration](#security-configuration)
6. [Performance Optimization](#performance-optimization)
7. [Monitoring and Analytics](#monitoring-and-analytics)
8. [Troubleshooting](#troubleshooting)
9. [Advanced Features](#advanced-features)

---

## Overview

Cloudflare provides:
- **Global CDN**: Content delivery from 300+ edge locations
- **DDoS Protection**: Automatic mitigation of DDoS attacks
- **Web Application Firewall (WAF)**: Protection against OWASP Top 10
- **Rate Limiting**: Edge-level rate limiting before traffic reaches your backend
- **SSL/TLS**: Free SSL certificates and HTTPS encryption
- **Analytics**: Real-time traffic analytics and security insights

### Architecture

```
Internet Users
      ↓
Cloudflare Edge Network (300+ locations)
      ↓ (Proxy)
Your Backend Application
      ↓
Database / Redis / Storage
```

Cloudflare sits between users and your backend, inspecting and filtering all traffic.

---

## Quick Start

### 1. Enable Cloudflare Proxy Mode

**Backend Configuration:**

Add this environment variable to your `.env` or deployment config:

```bash
# Enable Cloudflare IP range detection
CLOUDFLARE_PROXIES=true
```

This tells the backend to:
- Trust Cloudflare IP ranges automatically
- Use `CF-Connecting-IP` header for real client IPs
- Log Cloudflare metadata (CF-Ray, CF-IPCountry, etc.)

### 2. Verify Configuration

Test that Cloudflare headers are being detected:

```bash
# Make a request through Cloudflare
curl -v https://your-domain.com/health/ready

# Check logs for:
# "Using CF-Connecting-IP: <your-ip>"
# "CF-Ray: <ray-id>"
```

### 3. Check Rate Limiting Works

Verify individual user rate limiting (not treating all users as one IP):

```bash
# Trigger rate limit from your IP
for i in {1..6}; do
  curl -X POST https://your-domain.com/2fa/login \
    -d "username=test&password=wrong"
done

# You should be blocked, but other users should still work fine
```

---

## Backend Configuration

### Environment Variables

```bash
# === CLOUDFLARE INTEGRATION ===

# Enable automatic Cloudflare IP range detection
# When true, automatically trusts requests from Cloudflare's IP ranges
# and uses CF-Connecting-IP header for client IPs
CLOUDFLARE_PROXIES=true

# === ALTERNATIVE: MANUAL PROXY CONFIGURATION ===

# If not using Cloudflare, manually specify trusted proxy IPs
# Example: Your own load balancer or reverse proxy
# TRUSTED_PROXIES=10.0.0.1,172.16.0.1

# === RATE LIMITING ===

# These apply to application-level rate limiting
# (Cloudflare edge rate limiting is configured separately)
RATE_LIMIT_MAX_ATTEMPTS=5
RATE_LIMIT_LOCKOUT_MINUTES=60
RATE_LIMIT_WINDOW_MINUTES=15

# === ENVIRONMENT ===

# Set to 'production' for strict security headers
ENVIRONMENT=production
```

### Docker Compose Example

```yaml
version: '3.8'

services:
  backend:
    image: your-backend:latest
    environment:
      # Cloudflare integration
      - CLOUDFLARE_PROXIES=true

      # Rate limiting
      - RATE_LIMIT_MAX_ATTEMPTS=5
      - RATE_LIMIT_LOCKOUT_MINUTES=60
      - RATE_LIMIT_WINDOW_MINUTES=15

      # Security
      - ENVIRONMENT=production

      # Database
      - DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/surfsense

      # Redis (for rate limiting)
      - CELERY_BROKER_URL=redis://redis:6379/0

    depends_on:
      - db
      - redis

  db:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_PASSWORD=your-password

  redis:
    image: redis:7-alpine
```

### Kubernetes ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: backend-config
  namespace: production
data:
  CLOUDFLARE_PROXIES: "true"
  RATE_LIMIT_MAX_ATTEMPTS: "5"
  RATE_LIMIT_LOCKOUT_MINUTES: "60"
  RATE_LIMIT_WINDOW_MINUTES: "15"
  ENVIRONMENT: "production"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: production
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: backend
        image: your-backend:latest
        envFrom:
        - configMapRef:
            name: backend-config
        ports:
        - containerPort: 8000
```

---

## Cloudflare Dashboard Settings

### SSL/TLS Configuration

**Recommended Settings:**

1. **SSL/TLS** → **Overview**
   - **Encryption Mode**: `Full (strict)`
   - ✅ Why: Encrypts traffic between Cloudflare and your origin
   - ⚠️ Don't use "Flexible" - traffic to origin would be unencrypted

2. **Edge Certificates**
   - **Always Use HTTPS**: ✅ ON
   - **HSTS**: ✅ ENABLE
     - Max Age: `6 months` (15768000 seconds)
     - Include subdomains: ✅ ON
     - Preload: ✅ ON (if you've submitted to HSTS preload list)

3. **Minimum TLS Version**: `TLS 1.2` (or `TLS 1.3` for better security)

### DNS Configuration

For each domain/subdomain:

```
Type    Name              Content             Proxy Status
A       @                 your-ip             Proxied 🟠
A       api               your-api-ip         Proxied 🟠
AAAA    @                 your-ipv6           Proxied 🟠
CNAME   www               your-domain.com     Proxied 🟠
```

**Important**: Orange cloud (🟠) must be enabled for Cloudflare protection to work.

### Firewall Rules

Create rules to protect your application:

#### Rule 1: Block Malicious Countries (Optional)

```
Field: Country
Operator: equals
Value: [Select countries with high attack rates]
Action: Block
```

#### Rule 2: Allow Health Checks

```
Field: URI Path
Operator: equals
Value: /health
AND
Field: IP Address
Operator: is in
Value: [Your monitoring service IPs]
Action: Allow
```

#### Rule 3: Challenge Suspicious Patterns

```
Field: Threat Score
Operator: greater than
Value: 10
Action: Managed Challenge
```

#### Rule 4: Rate Limit Login Attempts (Edge Level)

```
Field: URI Path
Operator: equals
Value: /2fa/login
AND
Field: Request Method
Operator: equals
Value: POST
Rate: 10 requests per 1 minute
Action: Block for 10 minutes
```

### WAF (Web Application Firewall)

**Security** → **WAF** → **Managed Rules**

Enable these rulesets:

- ✅ **Cloudflare Managed Ruleset** - Core protection
- ✅ **Cloudflare OWASP Core Ruleset** - OWASP Top 10 protection
- ✅ **Cloudflare Exposed Credentials Check** - Prevent compromised credentials

**Sensitivity Level**: `Medium` (adjust based on false positives)

### Rate Limiting (Edge Level)

**Security** → **WAF** → **Rate Limiting Rules**

Create rate limiting rules at the edge (before traffic reaches your backend):

#### Login Endpoint Protection

```yaml
Rule Name: Login Rate Limit
If incoming requests match:
  - URI Path equals "/2fa/login"
  - Method equals "POST"

When rate exceeds:
  - 10 requests per 1 minute

Then:
  - Block for 10 minutes
  - Challenge for subsequent attempts

Characteristics:
  - Count requests by: IP Address
```

#### API Rate Limiting

```yaml
Rule Name: API Rate Limit
If incoming requests match:
  - URI Path starts with "/api/"
  - Method is not "GET"

When rate exceeds:
  - 100 requests per 1 minute

Then:
  - Challenge for 5 minutes

Characteristics:
  - Count requests by: IP Address
```

### DDoS Protection

**Security** → **DDoS**

- **HTTP DDoS Attack Protection**: ✅ ENABLED (Automatic mitigation)
- **Sensitivity Level**: `Medium`
- **Advanced DDoS Protection**: ✅ ENABLED (if on Enterprise plan)

### Bot Management

**Security** → **Bots**

**Free/Pro Plans:**
- **Bot Fight Mode**: ✅ ON
  - Blocks known malicious bots
  - Challenges suspected bots

**Business/Enterprise Plans:**
- **Bot Management**: ✅ ENABLED
  - Configure allowed bots (search engines, monitoring services)
  - Block automated scraping and credential stuffing

### Page Rules

Create page rules for specific behaviors:

#### API Caching

```
URL Pattern: *api.your-domain.com/*
Settings:
  - Cache Level: Bypass
  - Security Level: Medium
```

#### Static Assets Caching

```
URL Pattern: *your-domain.com/static/*
Settings:
  - Cache Level: Cache Everything
  - Edge Cache TTL: 1 month
  - Browser Cache TTL: 1 month
```

---

## Security Configuration

### Content Security Policy (CSP)

The backend automatically sets CSP headers. Cloudflare will pass them through.

**Verify CSP is working:**

```bash
curl -I https://your-domain.com | grep -i content-security-policy
```

**Example output:**
```
content-security-policy: default-src 'self'; script-src 'self'; ...
```

### Security Headers

The backend sets these headers automatically:

- `Strict-Transport-Security` (HSTS)
- `X-Content-Type-Options`
- `X-Frame-Options`
- `X-XSS-Protection`
- `Content-Security-Policy`
- `Referrer-Policy`
- `Permissions-Policy`

**Cloudflare will NOT override these** if you configure SSL/TLS to "Full (strict)".

### IP Geolocation and Blocking

Use `CF-IPCountry` header for geo-based security decisions.

**Example: Block high-risk countries at application level:**

```python
from fastapi import Request, HTTPException

BLOCKED_COUNTRIES = {"CN", "RU", "KP"}  # Example only

async def check_country(request: Request):
    country = request.headers.get("cf-ipcountry", "XX")
    if country in BLOCKED_COUNTRIES:
        raise HTTPException(403, "Access denied from your region")
```

### Cloudflare Access (Optional)

For admin endpoints, add an extra authentication layer:

1. **Access** → **Applications** → **Add an application**
2. **Application Type**: Self-hosted
3. **Name**: SurfSense Admin
4. **Session Duration**: 8 hours
5. **Application Domain**: admin.your-domain.com
6. **Identity Providers**: Configure (Google, GitHub, etc.)
7. **Policies**: Create allow policy for admin emails

This adds SSO authentication BEFORE requests reach your backend.

---

## Performance Optimization

### Caching Strategy

#### What to Cache

**Static Assets** (CSS, JS, images):
```
Cache-Control: public, max-age=31536000, immutable
```

**API Responses** (GET requests with short TTL):
```
Cache-Control: public, max-age=300, s-maxage=600
```

**Sensitive/Dynamic Endpoints** (login, user data):
```
Cache-Control: private, no-cache, no-store, must-revalidate
```

#### Cloudflare Cache Rules

**Rules** → **Page Rules** or **Cache Rules**:

```yaml
# Rule 1: Bypass cache for API mutations
URL: *your-domain.com/api/*
Method: POST, PUT, DELETE, PATCH
Cache Level: Bypass

# Rule 2: Cache static assets aggressively
URL: *your-domain.com/static/*
Cache Level: Cache Everything
Edge Cache TTL: 1 month
Browser Cache TTL: 1 month

# Rule 3: Short cache for GET APIs
URL: *your-domain.com/api/*
Method: GET
Cache Level: Standard
Edge Cache TTL: 5 minutes
```

### Argo Smart Routing

**Speed** → **Optimization** → **Argo Smart Routing**

- ✅ ENABLE (Business/Enterprise plans)
- Routes traffic through Cloudflare's fastest paths
- Reduces latency by up to 30%
- Costs $0.10 per GB

### HTTP/3 (QUIC)

**Network** → **HTTP/3 (with QUIC)**

- ✅ ENABLE
- Faster connection establishment
- Better performance on mobile/unreliable networks

### Early Hints

**Speed** → **Optimization** → **Early Hints**

- ✅ ENABLE
- Sends preload hints before full response
- Improves page load time

### Load Balancing (Optional)

For multiple origin servers:

1. **Traffic** → **Load Balancing** → **Create Load Balancer**
2. Add origin pools (multiple backend servers)
3. Configure health checks (use `/health/ready` endpoint)
4. Set failover policies

---

## Monitoring and Analytics

### Cloudflare Analytics

**Analytics** → **Traffic**

Monitor:
- Requests per second
- Bandwidth usage
- Response status codes (look for 429, 500, 503)
- Top countries/IPs
- Threats mitigated

### Security Events

**Security** → **Analytics**

- Firewall events (blocked, challenged, allowed)
- Rate limiting triggers
- Bot detection
- WAF rule hits

### Logs (Enterprise Only)

**Analytics** → **Logs**

- **Logpush**: Stream logs to S3, GCS, Azure, Datadog, etc.
- **Logpull**: Download logs via API

**Useful for:**
- Security incident investigation
- Performance analysis
- Correlating CF-Ray IDs with backend errors

### Custom Analytics with Workers (Optional)

Create a Cloudflare Worker to log custom metrics:

```javascript
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const response = await fetch(request)

  // Log custom metrics
  const metrics = {
    url: request.url,
    method: request.method,
    cf_ray: request.headers.get('cf-ray'),
    cf_country: request.headers.get('cf-ipcountry'),
    status: response.status,
    timestamp: Date.now()
  }

  // Send to your analytics endpoint
  fetch('https://your-analytics.com/log', {
    method: 'POST',
    body: JSON.stringify(metrics)
  })

  return response
}
```

### Correlating Logs

When investigating issues, correlate using `CF-Ray`:

1. **User reports issue** → Get CF-Ray from error page or support request
2. **Cloudflare Dashboard** → Search by CF-Ray to see edge logs
3. **Backend Logs** → Search `security_events` table:
   ```sql
   SELECT * FROM security_events
   WHERE details->>'cloudflare'->>'cf_ray' = '1234567890abc-SJC';
   ```

---

## Troubleshooting

### Issue: All users appear as single IP

**Symptoms:**
- Rate limiting affects all users together
- All requests show Cloudflare IP in logs

**Cause:** Backend not configured for Cloudflare

**Solution:**
```bash
# Add to .env
CLOUDFLARE_PROXIES=true

# Restart backend
docker-compose restart backend

# Verify
curl -v https://your-domain.com/health | grep CF-Connecting-IP
```

### Issue: SSL/TLS errors

**Symptoms:**
- `ERR_TOO_MANY_REDIRECTS`
- `SSL handshake failed`

**Cause:** Incorrect SSL mode

**Solution:**
1. **Cloudflare Dashboard** → **SSL/TLS** → **Overview**
2. Set to `Full (strict)`
3. Ensure your origin has valid SSL certificate

### Issue: Rate limiting too aggressive

**Symptoms:**
- Legitimate users being blocked
- High rate of 429 errors

**Solution:**

**Option 1: Adjust backend rate limits**
```bash
# Increase limits
RATE_LIMIT_MAX_ATTEMPTS=10
RATE_LIMIT_LOCKOUT_MINUTES=30
```

**Option 2: Adjust Cloudflare edge rate limits**
1. **Security** → **WAF** → **Rate Limiting Rules**
2. Increase thresholds or change action to "Challenge" instead of "Block"

**Option 3: Whitelist specific IPs**
1. **Security** → **WAF** → **Tools**
2. **IP Access Rules** → **Add Rule**
3. Action: `Allow`, IP/Range: `1.2.3.4`

### Issue: Cloudflare headers not present

**Symptoms:**
- `CF-Ray`, `CF-IPCountry` not in logs
- `get_cloudflare_metadata()` returns empty

**Cause:** Traffic not proxied through Cloudflare

**Solution:**
1. Check DNS proxy status (orange cloud 🟠)
2. Verify not accessing origin IP directly
3. Check firewall not allowing direct origin access

### Issue: Health checks failing

**Symptoms:**
- Load balancer marking origin as down
- Cloudflare health checks failing

**Solution:**

**Option 1: Check health endpoint**
```bash
# Direct to origin
curl http://your-origin-ip:8000/health/ready

# Through Cloudflare
curl https://your-domain.com/health/ready
```

**Option 2: Configure Cloudflare firewall exception**
```
Field: URI Path
Operator: equals
Value: /health/ready
Action: Allow
```

**Option 3: Use basic health check**
```
Health Check URL: https://your-domain.com/health
Expected Code: 200
```

### Issue: False positive WAF blocks

**Symptoms:**
- Legitimate requests blocked by WAF
- Users see "This website is using a security service..."

**Solution:**

**Option 1: Adjust WAF sensitivity**
1. **Security** → **WAF** → **Managed Rules**
2. Change sensitivity from "High" to "Medium" or "Low"

**Option 2: Create bypass rule**
1. **Security** → **WAF** → **Firewall Rules**
2. Create rule to skip WAF for specific patterns:
   ```
   URI Path equals /api/upload
   AND User Agent contains "YourApp/1.0"
   Action: Skip WAF
   ```

### Issue: Slow performance

**Symptoms:**
- High latency despite Cloudflare
- Slow page loads

**Diagnostics:**

**Check Cloudflare cache status:**
```bash
curl -I https://your-domain.com/api/endpoint | grep cf-cache-status

# Possible values:
# HIT - Served from cache (fast)
# MISS - Fetched from origin (slower)
# BYPASS - Caching disabled for this URL
# EXPIRED - Cache expired, revalidating
```

**Solutions:**

1. **Enable caching for cacheable endpoints**
   - Review cache rules
   - Add `Cache-Control` headers to responses

2. **Enable Argo Smart Routing** (if on Business+ plan)

3. **Enable HTTP/3**

4. **Optimize origin performance**
   - Review backend logs for slow queries
   - Add database indexes
   - Enable Redis caching

---

## Advanced Features

### Cloudflare Turnstile (CAPTCHA Alternative)

Turnstile is Cloudflare's privacy-friendly CAPTCHA replacement.

**Use Case:** Add to login after 2-3 failed attempts, before hard rate limit.

**Implementation:**

1. **Get Site Key & Secret Key**
   - **Cloudflare Dashboard** → **Turnstile**
   - Create site → Get `sitekey` and `secret`

2. **Frontend Integration**
   ```html
   <!-- Add Turnstile widget to login form -->
   <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>

   <form id="login-form">
     <input type="email" name="email" />
     <input type="password" name="password" />

     <!-- Turnstile widget -->
     <div class="cf-turnstile"
          data-sitekey="your-site-key"
          data-callback="onTurnstileSuccess"></div>

     <button type="submit">Login</button>
   </form>
   ```

3. **Backend Verification**
   ```python
   import httpx
   from fastapi import HTTPException

   async def verify_turnstile(token: str, ip: str) -> bool:
       """Verify Cloudflare Turnstile token."""
       async with httpx.AsyncClient() as client:
           response = await client.post(
               "https://challenges.cloudflare.com/turnstile/v0/siteverify",
               json={
                   "secret": "your-secret-key",
                   "response": token,
                   "remoteip": ip,
               }
           )
           data = response.json()
           return data.get("success", False)

   @router.post("/2fa/login")
   async def login(
       turnstile_token: str,
       ip_address: str | None = Depends(check_rate_limit),
   ):
       # After 3 failed attempts, require Turnstile
       if failed_attempts >= 3:
           if not turnstile_token or not await verify_turnstile(turnstile_token, ip_address):
               raise HTTPException(403, "CAPTCHA verification failed")

       # Proceed with normal login...
   ```

### Cloudflare Workers for Custom Logic

Deploy serverless functions at the edge:

```javascript
// Example: Add custom security headers
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const response = await fetch(request)

  // Clone response to modify headers
  const newResponse = new Response(response.body, response)

  // Add custom headers
  newResponse.headers.set('X-Custom-Security', 'enabled')
  newResponse.headers.set('X-Request-ID', crypto.randomUUID())

  return newResponse
}
```

### Waiting Room (Enterprise Feature)

Queue users during traffic spikes:

1. **Traffic** → **Waiting Room** → **Create**
2. Configure:
   - Path: `/` or `/login`
   - Total active users: 10,000
   - New users per minute: 100
   - Session duration: 15 minutes

### Rate Limiting with Adaptive Thresholds

Use Workers to implement smart rate limiting:

```javascript
// Adaptive rate limiting based on threat score
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const ip = request.headers.get('cf-connecting-ip')
  const threatScore = request.cf.threatScore || 0

  // Stricter limits for suspicious IPs
  const limit = threatScore > 30 ? 5 : 50

  // Check rate limit in KV storage
  const key = `ratelimit:${ip}`
  const count = await RATE_LIMIT.get(key) || 0

  if (count > limit) {
    return new Response('Rate limit exceeded', { status: 429 })
  }

  await RATE_LIMIT.put(key, count + 1, { expirationTtl: 60 })

  return fetch(request)
}
```

---

## Best Practices Summary

### ✅ DO

- **Enable Cloudflare proxy** (orange cloud 🟠) for all domains
- **Use Full (strict) SSL mode** for end-to-end encryption
- **Set CLOUDFLARE_PROXIES=true** in backend configuration
- **Configure WAF** with OWASP ruleset
- **Enable rate limiting** at both edge and application level
- **Monitor CF-Ray IDs** for troubleshooting
- **Use health check endpoints** for monitoring
- **Enable HSTS** with long max-age
- **Review analytics weekly** for attack patterns
- **Test failover scenarios** regularly

### ❌ DON'T

- **Don't use Flexible SSL** - traffic to origin would be unencrypted
- **Don't bypass Cloudflare** for sensitive endpoints
- **Don't trust CF-Connecting-IP** without CLOUDFLARE_PROXIES=true
- **Don't expose origin IP** - use firewall to block direct access
- **Don't cache sensitive data** - use `Cache-Control: private, no-store`
- **Don't ignore security alerts** from Cloudflare
- **Don't disable Bot Fight Mode** without a good reason
- **Don't forget to rotate Cloudflare API tokens** periodically

---

## Support and Resources

### Official Documentation

- [Cloudflare Docs](https://developers.cloudflare.com/)
- [API Documentation](https://developers.cloudflare.com/api/)
- [Community Forum](https://community.cloudflare.com/)

### Monitoring Tools

- **Cloudflare Radar**: https://radar.cloudflare.com/
- **Cloudflare Status**: https://www.cloudflarestatus.com/

### Getting Help

1. **Cloudflare Support** (if on paid plan)
2. **Community Forum** for technical questions
3. **Review application logs** and `security_events` table
4. **Check CF-Ray ID** when reporting issues

---

## Changelog

### 2025-01-21
- Initial Cloudflare setup guide
- Backend integration with CF-Connecting-IP
- Cloudflare IP range detection
- Health check endpoints
- Monitoring and logging recommendations

---

## Next Steps

After completing this setup:

1. ✅ Test rate limiting with multiple IPs
2. ✅ Verify CF-Ray logging in `security_events`
3. ✅ Configure monitoring alerts for 429/503 errors
4. ✅ Set up Logpush (if Enterprise) or log aggregation
5. ✅ Review WAF events weekly for false positives
6. ✅ Consider adding Turnstile for authentication endpoints
7. ✅ Document your specific Cloudflare configuration

For security issues or questions, refer to `SECURITY_IMPROVEMENTS.md`.
