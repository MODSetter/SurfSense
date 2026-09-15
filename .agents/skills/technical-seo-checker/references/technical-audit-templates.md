# Technical SEO Checker — Output Templates

Detailed output templates for technical-seo-checker steps 3-9. Referenced from [SKILL.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/technical-seo-checker/SKILL.md).

---

## Step 3: Audit Site Speed & Core Web Vitals

```markdown
## Performance Analysis

### Core Web Vitals

| Metric | Mobile | Desktop | Target | Status |
|--------|--------|---------|--------|--------|
| LCP (Largest Contentful Paint) | [X]s | [X]s | <2.5s | ✅/⚠️/❌ |
| FID (First Input Delay) | [X]ms | [X]ms | <100ms | ✅/⚠️/❌ |
| CLS (Cumulative Layout Shift) | [X] | [X] | <0.1 | ✅/⚠️/❌ |
| INP (Interaction to Next Paint) | [X]ms | [X]ms | <200ms | ✅/⚠️/❌ |

### Additional Performance Metrics

| Metric | Value | Status |
|--------|-------|--------|
| Time to First Byte (TTFB) | [X]ms | ✅/⚠️/❌ |
| First Contentful Paint (FCP) | [X]s | ✅/⚠️/❌ |
| Speed Index | [X] | ✅/⚠️/❌ |
| Total Blocking Time | [X]ms | ✅/⚠️/❌ |
| Page Size | [X]MB | ✅/⚠️/❌ |
| Requests | [X] | ✅/⚠️/❌ |

### Performance Issues

**LCP Issues**:
- [Issue]: [Impact] - [Solution]
- [Issue]: [Impact] - [Solution]

**CLS Issues**:
- [Issue]: [Impact] - [Solution]

**Resource Loading**:
| Resource Type | Count | Size | Issues |
|---------------|-------|------|--------|
| Images | [X] | [X]MB | [notes] |
| JavaScript | [X] | [X]MB | [notes] |
| CSS | [X] | [X]KB | [notes] |
| Fonts | [X] | [X]KB | [notes] |

### Optimization Recommendations

**High Impact**:
1. [Recommendation] - Est. improvement: [X]s
2. [Recommendation] - Est. improvement: [X]s

**Medium Impact**:
1. [Recommendation]
2. [Recommendation]

**Performance Score**: [X]/10
```

---

## Step 4: Audit Mobile-Friendliness

```markdown
## Mobile Optimization Analysis

### Mobile-Friendly Test

| Check | Status | Notes |
|-------|--------|-------|
| Mobile-friendly overall | ✅/❌ | [notes] |
| Viewport configured | ✅/❌ | [viewport tag] |
| Text readable | ✅/⚠️/❌ | Font size: [X]px |
| Tap targets sized | ✅/⚠️/❌ | [notes] |
| Content fits viewport | ✅/❌ | [notes] |
| No horizontal scroll | ✅/❌ | [notes] |

### Responsive Design Check

| Element | Desktop | Mobile | Issues |
|---------|---------|--------|--------|
| Navigation | [status] | [status] | [notes] |
| Images | [status] | [status] | [notes] |
| Forms | [status] | [status] | [notes] |
| Tables | [status] | [status] | [notes] |
| Videos | [status] | [status] | [notes] |

### Mobile-First Indexing

| Check | Status | Notes |
|-------|--------|-------|
| Mobile version has all content | ✅/⚠️/❌ | [notes] |
| Mobile has same structured data | ✅/⚠️/❌ | [notes] |
| Mobile has same meta tags | ✅/⚠️/❌ | [notes] |
| Mobile images have alt text | ✅/⚠️/❌ | [notes] |

**Mobile Score**: [X]/10
```

---

## Step 5: Audit Security & HTTPS

```markdown
## Security Analysis

### HTTPS Status

| Check | Status | Notes |
|-------|--------|-------|
| SSL certificate valid | ✅/❌ | Expires: [date] |
| HTTPS enforced | ✅/❌ | [redirects properly?] |
| Mixed content | ✅/⚠️/❌ | [X] issues |
| HSTS enabled | ✅/⚠️ | [notes] |
| Certificate chain | ✅/⚠️/❌ | [notes] |

### Security Headers

| Header | Present | Value | Recommended |
|--------|---------|-------|-------------|
| Content-Security-Policy | ✅/❌ | [value] | [recommendation] |
| X-Frame-Options | ✅/❌ | [value] | DENY or SAMEORIGIN |
| X-Content-Type-Options | ✅/❌ | [value] | nosniff |
| X-XSS-Protection | ✅/❌ | [value] | 1; mode=block |
| Referrer-Policy | ✅/❌ | [value] | [recommendation] |

**Security Score**: [X]/10
```

---

## Step 6: Audit URL Structure

```markdown
## URL Structure Analysis

### URL Pattern Review

| Check | Status | Notes |
|-------|--------|-------|
| HTTPS URLs | ✅/⚠️/❌ | [X]% HTTPS |
| Lowercase URLs | ✅/⚠️/❌ | [notes] |
| No special characters | ✅/⚠️/❌ | [notes] |
| Readable/descriptive | ✅/⚠️/❌ | [notes] |
| Appropriate length | ✅/⚠️/❌ | Avg: [X] chars |
| Keywords in URLs | ✅/⚠️/❌ | [notes] |
| Consistent structure | ✅/⚠️/❌ | [notes] |

### URL Issues Found

| Issue Type | Count | Examples |
|------------|-------|----------|
| Dynamic parameters | [X] | [URLs] |
| Session IDs in URLs | [X] | [URLs] |
| Uppercase characters | [X] | [URLs] |
| Special characters | [X] | [URLs] |
| Very long URLs (>100) | [X] | [URLs] |

### Redirect Analysis

| Check | Status | Notes |
|-------|--------|-------|
| Redirect chains | [X] found | [max chain length] |
| Redirect loops | [X] found | [URLs] |
| 302 → 301 needed | [X] found | [URLs] |
| Broken redirects | [X] found | [URLs] |

**URL Score**: [X]/10
```

---

## Step 7: Audit Structured Data

> **CORE-EEAT alignment**: Schema markup quality maps to O05 (Schema Markup) in the CORE-EEAT benchmark. See [content-quality-auditor](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/content-quality-auditor/SKILL.md) for full content quality audit.

```markdown
## Structured Data Analysis

### Schema Markup Found

| Schema Type | Pages | Valid | Errors |
|-------------|-------|-------|--------|
| [Type 1] | [X] | ✅/❌ | [errors] |
| [Type 2] | [X] | ✅/❌ | [errors] |

### Validation Results

**Errors**:
- [Error 1]: [affected pages] - [solution]
- [Error 2]: [affected pages] - [solution]

**Warnings**:
- [Warning 1]: [notes]

### Missing Schema Opportunities

| Page Type | Current Schema | Recommended |
|-----------|----------------|-------------|
| Blog posts | [current] | Article + FAQ |
| Products | [current] | Product + Review |
| Homepage | [current] | Organization |

**Structured Data Score**: [X]/10
```

---

## Step 8: Audit International SEO (if applicable)

```markdown
## International SEO Analysis

### Hreflang Implementation

| Check | Status | Notes |
|-------|--------|-------|
| Hreflang tags present | ✅/❌ | [notes] |
| Self-referencing | ✅/⚠️/❌ | [notes] |
| Return tags present | ✅/⚠️/❌ | [notes] |
| Valid language codes | ✅/⚠️/❌ | [notes] |
| x-default tag | ✅/⚠️ | [notes] |

### Language/Region Targeting

| Language | URL | Hreflang | Status |
|----------|-----|----------|--------|
| [en-US] | [URL] | [tag] | ✅/⚠️/❌ |
| [es-ES] | [URL] | [tag] | ✅/⚠️/❌ |

**International Score**: [X]/10
```

---

## Step 9: Generate Technical Audit Summary

```markdown
# Technical SEO Audit Report

**Domain**: [domain]
**Audit Date**: [date]
**Pages Analyzed**: [X]

## Overall Technical Health: [X]/100

```
Score Breakdown:
████████░░ Crawlability: 8/10
███████░░░ Indexability: 7/10
█████░░░░░ Performance: 5/10
████████░░ Mobile: 8/10
█████████░ Security: 9/10
██████░░░░ URL Structure: 6/10
█████░░░░░ Structured Data: 5/10
```

## Critical Issues (Fix Immediately)

1. **[Issue]**: [Impact]
   - Affected: [pages/scope]
   - Solution: [specific fix]
   - Priority: 🔴 Critical

2. **[Issue]**: [Impact]
   - Affected: [pages/scope]
   - Solution: [specific fix]
   - Priority: 🔴 Critical

## High Priority Issues

1. **[Issue]**: [Solution]
2. **[Issue]**: [Solution]

## Medium Priority Issues

1. **[Issue]**: [Solution]
2. **[Issue]**: [Solution]

## Quick Wins

These can be fixed quickly for immediate improvement:

1. [Quick fix 1]
2. [Quick fix 2]
3. [Quick fix 3]

## Implementation Roadmap

### Week 1: Critical Fixes
- [ ] [Task 1]
- [ ] [Task 2]

### Week 2-3: High Priority
- [ ] [Task 1]
- [ ] [Task 2]

### Week 4+: Optimization
- [ ] [Task 1]
- [ ] [Task 2]

## Monitoring Recommendations

Set up alerts for:
- Core Web Vitals drops
- Crawl error spikes
- Index coverage changes
- Security issues
```
