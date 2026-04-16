# HTTP Status Codes for SEO

SEO-relevant HTTP status codes, their implications, and how to diagnose and fix issues.

## Status Code Categories

- **2xx**: Success - Request succeeded
- **3xx**: Redirection - Further action needed
- **4xx**: Client Error - Problem with the request
- **5xx**: Server Error - Server failed to fulfill request

---

## 2xx Success Codes

### 200 OK

**What it means**: Request succeeded, content returned normally.

**SEO impact**: Positive - page is accessible and indexable.

**When to use**: Standard response for all working pages.

**When it's a problem**: When different URLs return 200 for same content (should use 301 redirect).

---

### 204 No Content

**What it means**: Request succeeded but no content to return.

**SEO impact**: Neutral - rarely used for pages meant to be indexed.

**Common use**: API responses, AJAX requests.

---

## 3xx Redirection Codes

### 301 Moved Permanently

**What it means**: Resource permanently moved to new URL. All link equity transfers.

**SEO impact**: Positive when used correctly - passes 90-99% of link equity.

**When to use**:
- Permanently changing URL structure
- Consolidating duplicate content
- Moving to new domain
- Changing HTTP to HTTPS
- Changing www to non-www (or vice versa)

**Example header**:
```
HTTP/1.1 301 Moved Permanently
Location: https://example.com/new-page
```

**Common mistakes**:
- Using 302 instead of 301 for permanent changes
- Creating redirect chains (A→B→C)
- Redirecting to irrelevant pages
- Not redirecting HTTP to HTTPS

**How to implement**:
- **.htaccess** (Apache): `Redirect 301 /old-page /new-page`
- **nginx**: `rewrite ^/old-page$ /new-page permanent;`
- **Server-side**: Set Location header with 301 status

---

### 302 Found (Temporary Redirect)

**What it means**: Resource temporarily at different URL. Original URL should still be used.

**SEO impact**: Neutral to negative - does NOT pass full link equity. Search engines keep indexing original URL.

**When to use**:
- A/B testing
- Temporary promotions
- Maintenance redirects
- Geolocation redirects (sometimes)

**When NOT to use**: Permanent URL changes (use 301).

**Warning**: Google may treat long-standing 302s as 301s, but better to be explicit.

---

### 303 See Other

**What it means**: Response can be found at another URI using GET.

**SEO impact**: Minimal - rarely used for SEO purposes.

**Common use**: After form submissions, redirect to results page.

---

### 307 Temporary Redirect

**What it means**: Temporary redirect that preserves request method (POST stays POST).

**SEO impact**: Similar to 302 - temporary, doesn't pass full link equity.

**Difference from 302**: Guarantees request method won't change (more precise than 302).

**When to use**: Temporary redirects where HTTP method preservation matters.

---

### 308 Permanent Redirect

**What it means**: Permanent redirect that preserves request method.

**SEO impact**: Similar to 301 - passes link equity.

**Difference from 301**: Guarantees request method won't change (POST stays POST).

**When to use**: Permanent redirects where method preservation matters (rare for SEO).

---

### Redirect Chain Issues

**Problem**: Multiple redirects before reaching final destination.

**Example chain**:
```
http://example.com/page
  → https://example.com/page (redirect 1)
  → https://www.example.com/page (redirect 2)
  → https://www.example.com/new-page (redirect 3)
```

**SEO impact**:
- Slows page load (each redirect = new HTTP request)
- Dilutes link equity with each hop
- Wastes crawl budget
- Poor user experience

**How to fix**: Redirect directly from original URL to final destination.

**Fixed version**:
```
http://example.com/page
  → https://www.example.com/new-page (single redirect)
```

---

### Redirect Loops

**Problem**: Redirects create infinite loop.

**Example**:
```
/page-a → /page-b
/page-b → /page-a
```

**SEO impact**: Severe - page completely inaccessible.

**Symptoms**:
- Browser shows "Too many redirects" error
- Page never loads
- Search Console shows crawl errors

**How to diagnose**:
1. Use redirect checker tool
2. Check .htaccess or nginx config for conflicting rules
3. Review server-side redirect logic

**How to fix**:
1. Identify conflicting redirect rules
2. Remove or correct the loop
3. Test thoroughly
4. Request recrawl in Search Console

---

## 4xx Client Error Codes

### 404 Not Found

**What it means**: Requested resource doesn't exist.

**SEO impact**: Neutral to negative depending on context.

**When 404s are OK**:
- Legitimately deleted pages with no equivalent
- Never-existed URLs from typos
- Temporary content that expired (old promotions)
- Intentionally removed low-quality content

**When 404s are problems**:
- Pages that should exist are returning 404
- Previously working pages now broken
- Important pages missing from navigation
- High-traffic pages deleted without redirect

**How to fix**:
1. **If content moved**: Set up 301 redirect to new location
2. **If content deleted**: Either keep 404 or redirect to relevant category
3. **If never existed**: Leave as 404
4. **If important**: Restore the page

**Monitoring 404s**:
- Check Search Console → Coverage → Not found (404)
- Review referrer data to see what's linking to 404s
- Fix high-value 404s first (most traffic/backlinks)

**Soft 404s** (BAD):
- Page returns 200 but shows "not found" message
- Search engines may keep page indexed
- Creates duplicate content issues
- Fix: Return proper 404 status code

---

### 410 Gone

**What it means**: Resource permanently deleted, never coming back.

**SEO impact**: Stronger signal than 404 - tells search engines not to return.

**When to use**:
- Discontinued products
- Expired promotions
- Permanently removed content
- Outdated information

**Difference from 404**:
- 404: "Not found" (might exist at another URL)
- 410: "Gone forever" (don't look for it)

**When to use 410 vs 301**:
- Use 410: No equivalent replacement exists
- Use 301: Relevant alternative exists

**How search engines respond**:
- Faster de-indexing than 404
- Stop crawling sooner
- Better for crawl budget

---

### 403 Forbidden

**What it means**: Server understood request but refuses to authorize it.

**SEO impact**: Negative - page inaccessible and won't be indexed.

**Common causes**:
- Permission restrictions
- IP blocking
- .htaccess restrictions
- File permissions (chmod)
- Authentication required

**When it's intentional**:
- Admin areas
- Member-only content
- Geographic restrictions

**When it's a problem**:
- Public pages returning 403
- Search engine bots blocked
- Accidental permission changes

**How to diagnose**:
1. Check .htaccess for IP restrictions
2. Verify file permissions (should be 644 for files, 755 for directories)
3. Check server-level access rules
4. Test with different IPs/user-agents

**How to fix**:
1. Adjust file permissions: `chmod 644 filename`
2. Remove blocking rules from .htaccess
3. Whitelist search engine bots
4. Review server firewall rules

---

### 401 Unauthorized

**What it means**: Authentication required but not provided or failed.

**SEO impact**: Negative - page won't be indexed.

**Common causes**:
- Password-protected pages
- HTTP Basic Authentication
- Expired sessions
- Missing credentials

**When it's intentional**: Member areas, staging sites, admin panels.

**How to handle for SEO**:
- Don't password-protect pages you want indexed
- Use separate staging domain with 401
- For members-only content, show teaser with meta robots noindex

---

### 429 Too Many Requests

**What it means**: User/bot sent too many requests in given timeframe (rate limiting).

**SEO impact**: Negative if search engines can't crawl.

**Common causes**:
- Aggressive crawling
- DDoS protection triggered
- API rate limits
- Server throttling

**How to handle**:
1. Check Googlebot isn't being rate-limited (use Search Console)
2. Whitelist verified search engine bots
3. Configure rate limits appropriately
4. Monitor crawl rate in Search Console

---

## 5xx Server Error Codes

### 500 Internal Server Error

**What it means**: Generic server error, something went wrong.

**SEO impact**: Very negative if persistent - prevents indexing and ranking.

**Common causes**:
- PHP/code errors
- Database connection issues
- .htaccess syntax errors
- Resource limits exceeded
- Plugin/theme conflicts (WordPress)

**How to diagnose**:
1. Check server error logs
2. Review recent code/config changes
3. Test locally or on staging
4. Disable plugins one by one (if CMS)
5. Check .htaccess syntax

**How to fix**:
1. Review error logs for specific error
2. Roll back recent changes
3. Fix code errors
4. Increase resource limits if needed
5. Test thoroughly before re-deploying

**Monitoring**: Set up alerts for 500 errors (sudden spike = problem).

---

### 502 Bad Gateway

**What it means**: Server received invalid response from upstream server.

**SEO impact**: Negative if persistent - prevents crawling/indexing.

**Common causes**:
- Proxy/load balancer issues
- Upstream server down
- Timeout issues
- Firewall blocking

**Common scenarios**:
- CDN can't reach origin server
- Application server crashed
- Database server unresponsive

**How to fix**:
1. Check upstream server status
2. Verify firewall rules
3. Check timeout settings
4. Restart proxy/load balancer if needed
5. Review CDN configuration

---

### 503 Service Unavailable

**What it means**: Server temporarily unable to handle request.

**SEO impact**: Neutral if truly temporary with Retry-After header. Negative if prolonged.

**Common causes**:
- Maintenance mode
- Server overload
- Database down
- Resource exhaustion

**Proper use for maintenance**:
```
HTTP/1.1 503 Service Unavailable
Retry-After: 3600
```

**Best practices for maintenance**:
1. Use 503 (not 404 or 500)
2. Include Retry-After header
3. Keep maintenance brief (<24 hours)
4. Schedule during low-traffic times
5. Inform users with clear message

**How search engines handle 503**:
- Short-term (hours): Will retry, no ranking impact
- Long-term (days+): May drop rankings, de-index pages

---

### 504 Gateway Timeout

**What it means**: Server didn't receive timely response from upstream server.

**SEO impact**: Negative - prevents crawling.

**Common causes**:
- Slow database queries
- External API timeouts
- Insufficient server resources
- Network issues

**How to fix**:
1. Optimize slow queries
2. Increase timeout limits
3. Add caching
4. Scale server resources
5. Review external dependencies

---

## Status Code Decision Flowchart

### Content Moved Permanently?
→ YES: Use **301 redirect**
→ NO: Continue

### Content Moved Temporarily?
→ YES: Use **302 redirect**
→ NO: Continue

### Content Deleted with No Replacement?
→ YES: Use **404** (or **410** if permanently gone)
→ NO: Continue

### Content Exists at This URL?
→ YES: Use **200 OK**
→ NO: Use **404**

### Need Authentication?
→ YES: Use **401**
→ NO: Continue

### Access Forbidden?
→ YES: Use **403**
→ NO: Continue

### Server Error?
→ YES: Use **500**, **502**, **503**, or **504** depending on cause
→ NO: Use **200 OK**

---

## Diagnosing Status Code Issues

### Tools

**Browser DevTools**:
1. Open DevTools (F12)
2. Go to Network tab
3. Reload page
4. Check status code in first request

**cURL command**:
```bash
curl -I https://example.com/page
```

**Online checkers**:
- httpstatus.io
- redirect-checker.org
- websiteplanet.com/webtools/redirects/

**Google Search Console**:
- Coverage report → Error/Excluded sections
- URL Inspection tool → Check specific URLs

---

### Common Diagnostic Scenarios

### "Page Won't Index"

**Check**:
1. Status code (should be 200)
2. Redirects (shouldn't redirect away)
3. 4xx/5xx errors
4. robots.txt blocking
5. noindex meta tag

### "Page Disappeared from Results"

**Check**:
1. Returns 404/410/5xx
2. Redirecting elsewhere (301/302)
3. Changed to 403/401
4. Server timing out (504)

### "Traffic Dropped After Migration"

**Check**:
1. Old URLs return 404 (should be 301)
2. Redirect chains (should be direct)
3. Redirect loops
4. Wrong redirect type (302 vs 301)
5. Incorrect redirect targets

---

## Status Codes and Crawl Budget

### Impact on Crawl Budget

**Efficient (minimal impact)**:
- 200 OK
- 301 redirects (if minimal chains)
- 410 Gone (removes from crawl queue)

**Moderate impact**:
- 302 redirects (search engine may keep checking)
- 404 errors (search engines periodically recheck)
- Redirect chains (multiple requests per URL)

**High impact (wasteful)**:
- 5xx errors (search engines retry frequently)
- Redirect loops (waste crawl budget)
- Soft 404s (search engine confused, keeps crawling)
- 429 rate limiting (prevents efficient crawling)

---

## SEO Status Code Best Practices

### For Migrations

- [ ] Use 301 redirects for all permanently moved pages
- [ ] Redirect directly to final destination (no chains)
- [ ] Test all redirects before launching
- [ ] Keep redirects in place for at least 1 year
- [ ] Monitor 404 errors in Search Console post-launch
- [ ] Map 1:1 where possible (old URL → equivalent new URL)

### For Deleted Content

- [ ] Use 301 if relevant replacement exists
- [ ] Use 404 if no replacement and might return
- [ ] Use 410 if permanently gone, never returning
- [ ] Don't redirect to irrelevant pages (creates soft 404)
- [ ] Create custom 404 page with search and navigation

### For Maintenance

- [ ] Use 503 with Retry-After header
- [ ] Keep maintenance window brief (<24 hours)
- [ ] Create user-friendly maintenance page
- [ ] Inform users of expected downtime
- [ ] Monitor Search Console for crawl issues

### For Performance

- [ ] Minimize redirect chains
- [ ] Fix redirect loops immediately
- [ ] Monitor 5xx errors closely
- [ ] Set up alerts for sudden status code changes
- [ ] Optimize to reduce 504 timeouts

---

## Status Code Monitoring

### Key Metrics to Track

**In Search Console**:
- Crawl errors by type
- Server errors (5xx) trend
- Not found (404) trend
- Redirect errors

**In analytics**:
- 404 page views
- Entry pages with high exit rate (might be errors)
- Sudden traffic drops (could indicate status code issues)

**Server logs**:
- Status code distribution
- 5xx error frequency
- Unusual patterns

### Setting Up Alerts

**Alert on**:
- Sudden increase in 5xx errors
- Increase in 404 errors
- New redirect chains
- Crawl error spikes in Search Console

**Tools**:
- Google Search Console email alerts
- Server monitoring (UptimeRobot, Pingdom)
- Log analysis tools
- Custom scripts for log monitoring

---

## Quick Reference Table

| Code | Name | SEO Impact | Use When | Passes Link Equity? |
|------|------|------------|----------|---------------------|
| 200 | OK | ✅ Positive | Page works normally | N/A (original URL) |
| 301 | Moved Permanently | ✅ Positive | Permanent URL change | ✅ Yes (~90-99%) |
| 302 | Found | ⚠️ Neutral | Temporary redirect | ❌ No |
| 307 | Temporary Redirect | ⚠️ Neutral | Temporary (method preserved) | ❌ No |
| 308 | Permanent Redirect | ✅ Positive | Permanent (method preserved) | ✅ Yes |
| 404 | Not Found | ⚠️ Neutral | Content doesn't exist | N/A |
| 410 | Gone | ⚠️ Neutral | Permanent deletion | N/A |
| 403 | Forbidden | ❌ Negative | Access denied | N/A |
| 401 | Unauthorized | ❌ Negative | Auth required | N/A |
| 500 | Internal Server Error | ❌ Negative | Server error | N/A |
| 502 | Bad Gateway | ❌ Negative | Upstream error | N/A |
| 503 | Service Unavailable | ⚠️ Neutral | Temporary downtime | N/A |
| 504 | Gateway Timeout | ❌ Negative | Timeout error | N/A |

---

## Status Code Testing Checklist

Before launching site changes:

- [ ] Test all redirects return correct status codes
- [ ] Verify no redirect chains exist
- [ ] Check no redirect loops present
- [ ] Confirm important pages return 200
- [ ] Ensure deleted pages return 404/410 (not 200)
- [ ] Verify 301s point to correct destinations
- [ ] Test with multiple user-agents
- [ ] Check status codes in Search Console
- [ ] Monitor server logs for unusual patterns
- [ ] Set up alerts for error spikes

---

## Technical SEO Severity Framework

### Issue Classification

| Severity | Impact Description | Examples | Response Time |
|----------|-------------------|---------|---------------|
| **Critical** | Prevents indexation or causes site-wide issues | Robots.txt blocking site, noindex on key pages, site-wide 500 errors | Same day |
| **High** | Significantly impacts rankings or user experience | Slow page speed, missing hreflang, duplicate content, redirect chains | Within 1 week |
| **Medium** | Affects specific pages or has moderate impact | Missing schema, suboptimal canonicals, thin content pages | Within 1 month |
| **Low** | Minor optimization opportunities | Image compression, minor CLS issues, non-essential schema missing | Next quarter |

### Technical Debt Prioritization Matrix

| Factor | Weight | Assessment |
|--------|--------|-----------|
| Pages affected | 30% | Site-wide > Section > Single page |
| Revenue impact | 25% | Revenue pages > Blog > Utility pages |
| Fix difficulty | 20% | Config change < Template change < Code rewrite |
| Competitive impact | 15% | Competitors passing you > parity > you ahead |
| Crawl budget waste | 10% | High waste > Moderate > Minimal |

## Core Web Vitals Optimization Quick Reference

### LCP (Largest Contentful Paint) Optimization

| Root Cause | Detection | Fix |
|-----------|-----------|-----|
| Large hero image | PageSpeed Insights | Serve WebP, resize to container, add loading="lazy" |
| Render-blocking CSS/JS | DevTools Coverage | Defer non-critical, inline critical CSS |
| Slow server response | TTFB >800ms | CDN, server-side caching, upgrade hosting |
| Third-party scripts | DevTools Network | Defer/async, use facade pattern |

### CLS (Cumulative Layout Shift) Optimization

| Root Cause | Detection | Fix |
|-----------|-----------|-----|
| Images without dimensions | DevTools | Add explicit width/height attributes |
| Ads/embeds without reserved space | Visual inspection | Set min-height on containers |
| Web fonts causing FOUT | DevTools | font-display: swap + preload fonts |
| Dynamic content injection | Visual inspection | Reserve space with CSS |

### INP (Interaction to Next Paint) Optimization

| Root Cause | Detection | Fix |
|-----------|-----------|-----|
| Long JavaScript tasks | DevTools Performance | Break into smaller tasks, use requestIdleCallback |
| Heavy event handlers | DevTools | Debounce/throttle, use passive listeners |
| Main thread blocking | DevTools | Web workers for heavy computation |

