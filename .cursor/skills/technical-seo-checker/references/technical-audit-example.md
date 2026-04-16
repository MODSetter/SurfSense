# Technical SEO Checker — Worked Example & Checklist

Referenced from [SKILL.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/technical-seo-checker/SKILL.md).

---

## Worked Example

**User**: "Check the technical SEO of cloudhosting.com"

**Output**:

```markdown
# Technical SEO Audit Report

**Domain**: cloudhosting.com
**Audit Date**: 2024-09-15
**Pages Analyzed**: 312

## Crawlability Analysis

### Robots.txt Review

**URL**: cloudhosting.com/robots.txt
**Status**: Found

| Check | Status | Notes |
|-------|--------|-------|
| File exists | ✅ | 200 response |
| Valid syntax | ⚠️ | Wildcard pattern `Disallow: /*?` too aggressive — blocks faceted pages |
| Sitemap declared | ❌ | No Sitemap directive in robots.txt |
| Important pages blocked | ⚠️ | /pricing/ blocked by `Disallow: /pricing` rule |
| Assets blocked | ✅ | CSS/JS accessible |

**Issues Found**:
- Sitemap URL not declared in robots.txt
- `/pricing/` inadvertently blocked — high-value commercial page

### XML Sitemap Review

**Sitemap URL**: cloudhosting.com/sitemap.xml
**Status**: Found (not referenced in robots.txt)

| Check | Status | Notes |
|-------|--------|-------|
| Sitemap exists | ✅ | Valid XML, 287 URLs |
| Only indexable URLs | ❌ | 23 noindex URLs included |
| Includes lastmod | ⚠️ | All dates set to 2023-01-01 — not accurate |

**Crawlability Score**: 5/10

## Performance Analysis

### Core Web Vitals

| Metric | Mobile | Desktop | Target | Status |
|--------|--------|---------|--------|--------|
| LCP (Largest Contentful Paint) | 4.8s | 2.1s | <2.5s | ❌ Mobile / ✅ Desktop |
| FID (First Input Delay) | 45ms | 12ms | <100ms | ✅ / ✅ |
| CLS (Cumulative Layout Shift) | 0.24 | 0.08 | <0.1 | ❌ Mobile / ✅ Desktop |
| INP (Interaction to Next Paint) | 380ms | 140ms | <200ms | ❌ Mobile / ✅ Desktop |

### Additional Performance Metrics

| Metric | Value | Status |
|--------|-------|--------|
| Time to First Byte (TTFB) | 1,240ms | ❌ |
| Page Size | 3.8MB | ❌ |
| Requests | 94 | ⚠️ |

**LCP Issues**:
- Uncompressed hero image (2.4MB PNG): Convert to WebP, est. save 1.9MB
- No CDN detected: TTFB 1,240ms from origin server

**CLS Issues**:
- Ad banner at top of page injects without reserved height (0.18 shift contribution)

**Performance Score**: 3/10

## Security Analysis

### HTTPS Status

| Check | Status | Notes |
|-------|--------|-------|
| SSL certificate valid | ✅ | Expires: 2025-03-22 |
| HTTPS enforced | ⚠️ | http://cloudhosting.com returns 200 instead of 301 redirect |
| Mixed content | ❌ | 7 images loaded over HTTP on /features/ page |
| HSTS enabled | ❌ | Header not present |

**Security Score**: 5/10

## Structured Data Analysis

### Schema Markup Found

| Schema Type | Pages | Valid | Errors |
|-------------|-------|-------|--------|
| Organization | 1 (homepage) | ✅ | None |
| Article | 0 | — | Missing on 48 blog posts |
| Product | 0 | — | Missing on 5 plan pages |
| FAQ | 0 | — | Missing on 12 pages with FAQ content |

**Structured Data Score**: 3/10

## Overall Technical Health: 42/100

```
Score Breakdown:
█████░░░░░ Crawlability: 5/10
██████░░░░ Indexability: 6/10
███░░░░░░░ Performance: 3/10
██████░░░░ Mobile: 6/10
█████░░░░░ Security: 5/10
██████░░░░ URL Structure: 6/10
███░░░░░░░ Structured Data: 3/10
```

## Priority Issues

### 🔴 Critical (Fix Immediately)
1. **Mobile LCP 4.8s (target <2.5s)** — Compress hero image to WebP (est. save 1.9MB) and implement a CDN to reduce TTFB from 1,240ms to <400ms.

### 🟡 Important (Fix Soon)
2. **HTTP not redirecting to HTTPS** — Add 301 redirect from http:// to https:// and enable HSTS header. 7 mixed-content images on /features/ need URL updates.

### 🟢 Minor (Optimize)
3. **No Article/FAQ schema on blog posts** — Add Article schema to 48 blog posts and FAQ schema to 12 FAQ pages for rich result eligibility.
```

---

## Technical SEO Checklist

```markdown
### Crawlability
- [ ] robots.txt is valid and not blocking important content
- [ ] XML sitemap exists and is submitted to ~~search console
- [ ] No crawl errors in ~~search console
- [ ] No redirect chains or loops

### Indexability
- [ ] Important pages are indexable
- [ ] Canonical tags are correct
- [ ] No duplicate content issues
- [ ] Pagination is handled correctly

### Performance
- [ ] Core Web Vitals pass
- [ ] Page speed under 3 seconds
- [ ] Images are optimized
- [ ] JS/CSS are minified

### Mobile
- [ ] Mobile-friendly test passes
- [ ] Viewport is configured
- [ ] Touch elements are properly sized

### Security
- [ ] HTTPS is enforced
- [ ] SSL certificate is valid
- [ ] No mixed content
- [ ] Security headers present

### Structure
- [ ] URLs are clean and descriptive
- [ ] Site architecture is logical
- [ ] Internal linking is strong
```
