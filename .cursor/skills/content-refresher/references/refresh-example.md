# Content Refresher — Worked Example & Checklist

Referenced from [SKILL.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/content-refresher/SKILL.md).

---

## Worked Example

**User**: "Refresh my blog post about 'best cloud hosting providers'"

**Output**:

```markdown
### CORE-EEAT Quick Assessment

**Content**: "Best Cloud Hosting Providers 2023"
**Content Type**: Commercial comparison / listicle

| Dimension | Quick Score | Key Weakness | Refresh Priority |
|-----------|-----------|--------------|-----------------|
| C — Contextual Clarity | 60/100 | Title says 2023 — stale intent signal | 🔴 |
| O — Organization | 75/100 | Good comparison tables but no summary box | 🟡 |
| R — Referenceability | 35/100 | Pricing from Q1 2023, 3 broken links | 🔴 |
| E — Exclusivity | 50/100 | No original benchmarks or test data | 🟡 |
| Exp — Experience | 30/100 | No first-person testing narrative | 🔴 |
| Ept — Expertise | 65/100 | Author bio present but lacks credentials | 🟡 |
| A — Authority | 55/100 | 12 backlinks, was ranking page 1 | 🟢 |
| T — Trust | 60/100 | Affiliate links present but not disclosed | 🔴 |

**Weakest Dimensions** (focus refresh here):
1. **Experience** — Add hands-on testing results ("We migrated a test site to each provider")
2. **Referenceability** — Replace all 2023 pricing/uptime data with current figures

## Content Refresh Analysis: Best Cloud Hosting Providers 2023

**URL**: cloudhosting.com/best-cloud-hosting
**Published**: 2023-02-14
**Last Updated**: Never
**Word Count**: 2,100

### Performance Metrics

| Metric | 6 Mo Ago | Current | Change |
|--------|----------|---------|--------|
| Organic Traffic | 3,200/mo | 1,400/mo | -56% |
| Avg Position | 4.2 | 14.8 | ↓ 10.6 |
| Impressions | 18,000 | 9,500 | -47% |
| CTR | 6.1% | 2.3% | -3.8% |

### Content Decay Signals Identified

1. **Outdated year in title and H1** — "2023" signals stale content to users and search engines
2. **Pricing data 18+ months old** — AWS Lightsail listed at $3.50/mo (now $5/mo), DigitalOcean at $4/mo (now $6/mo)
3. **Missing new entrants** — No mention of Hetzner Cloud or Vultr, which 4/5 top competitors now cover
4. **3 broken outbound links** — Provider comparison pages that have moved or been retired

### Refresh vs. Rewrite Decision

| Factor | Assessment |
|--------|-----------|
| Content quality | Good structure, solid comparison tables — foundation is sound |
| URL equity | 12 referring domains, 18 months old |
| Scope of changes | ~40% of content needs updating |
| Search intent | Unchanged — still commercial comparison |

**Decision**: **REFRESH** — The URL has earned backlinks, the structure is solid, and less than 50% needs rewriting. Keep the URL, update in place.

## Content Refresh Plan

**Current Title**: "Best Cloud Hosting Providers 2023"
**Refreshed Title**: "Best Cloud Hosting Providers 2024: 7 Platforms Tested & Compared"

### Specific Refresh Actions

1. **Update all pricing and specs** (~30 min)
   - Replace 2023 pricing for all 5 listed providers with current data
   - Add uptime stats from the last 12 months (source: UptimeRobot public status pages)
   - Update feature comparison table with current plan tiers

2. **Add 2 missing providers + testing narrative** (~600 words)
   - Add Hetzner Cloud and Vultr sections with same comparison format
   - Write intro paragraph: "We deployed a WordPress benchmark site to each provider and measured TTFB, uptime, and support response times over 30 days"

3. **Add affiliate disclosure and FAQ section** (~200 words)
   - Add disclosure statement below introduction: "This post contains affiliate links. See our editorial policy."
   - Add FAQ with 4 questions targeting People Also Ask (e.g., "What is the cheapest cloud hosting?", "Is cloud hosting faster than shared hosting?")
   - Implement FAQ schema markup for rich result eligibility

4. **Fix broken links and update internal links** (~15 min)
   - Replace 3 broken outbound links with current provider URLs
   - Add internal links to cloudhosting.com/vps-vs-cloud and cloudhosting.com/hosting-speed-test

### Republishing Strategy

**Recommendation**: Update Published Date — this is a major overhaul (40%+ new content, new providers, fresh test data). Update `dateModified` in Article schema, resubmit URL in Search Console, and share on social as "Updated for 2024."

### Expected Outcomes

| Metric | Current | 30-Day Target | 90-Day Target |
|--------|---------|---------------|---------------|
| Avg Position | 14.8 | 8-10 | 3-6 |
| Organic Traffic | 1,400/mo | 2,200/mo | 3,500/mo |
| Featured Snippets | 0 | 1 (FAQ) | 2+ |
```

---

## Content Refresh Checklist

```markdown
### Pre-Refresh
- [ ] Analyze current performance metrics
- [ ] Identify outdated information
- [ ] Research competitor updates
- [ ] Note missing topics

### Content Updates
- [ ] Update year references
- [ ] Refresh statistics with sources
- [ ] Add new examples and case studies
- [ ] Expand thin sections
- [ ] Add new relevant sections
- [ ] Create FAQ section

### SEO Updates
- [ ] Update title tag
- [ ] Refresh meta description
- [ ] Optimize headers
- [ ] Update internal links
- [ ] Add new images with alt text

### GEO Updates
- [ ] Add clear definition
- [ ] Include quotable statements
- [ ] Add Q&A formatted content
- [ ] Update source citations

### Technical
- [ ] Update schema dateModified
- [ ] Clear page cache
- [ ] Update sitemap
- [ ] Test page speed
```
