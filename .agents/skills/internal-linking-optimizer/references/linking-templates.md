# Internal Linking Optimizer — Output Templates

Detailed output templates for internal-linking-optimizer steps 4-7. Referenced from [SKILL.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/internal-linking-optimizer/SKILL.md).

---

## Step 4: Create Topic Cluster Link Strategy

```markdown
## Topic Cluster Internal Linking

### Cluster: [Main Topic]

**Pillar Page**: [URL]
**Cluster Articles**: [X]

### Current Link Map

```
[Pillar Page]
   ├── [Cluster Article 1] ←→ [linked?]
   ├── [Cluster Article 2] ←→ [linked?]
   ├── [Cluster Article 3] ←→ [linked?]
   └── [Cluster Article 4] ←→ [linked?]
```

### Recommended Link Structure

```
[Pillar Page]
   ├── Links TO all cluster articles ✅
   │
   ├── [Cluster Article 1]
   │   ├── Link TO pillar ✅
   │   └── Link TO related cluster articles
   │
   ├── [Cluster Article 2]
   │   ├── Link TO pillar ✅
   │   └── Link TO related cluster articles
   │
   └── [etc.]
```

### Links to Add

| From Page | To Page | Anchor Text | Location |
|-----------|---------|-------------|----------|
| [URL 1] | [URL 2] | "[anchor]" | [paragraph/section] |
| [URL 2] | [URL 3] | "[anchor]" | [paragraph/section] |
| [Pillar] | [Cluster 1] | "[anchor]" | [section] |
```

---

## Step 5: Find Contextual Link Opportunities

```markdown
## Contextual Link Opportunities

### Link Opportunity Analysis

For each page, find relevant pages to link to based on:
- Topic relevance
- Keyword overlap
- User journey logic
- Authority distribution needs

### Opportunities Found

**Page: [URL 1]**
**Topic**: [topic]
**Current internal links**: [X]

| Opportunity | Target Page | Anchor Text | Why Link |
|-------------|-------------|-------------|----------|
| Paragraph 2 mentions "[topic]" | [URL] | "[topic phrase]" | Topic match |
| Section on "[subject]" | [URL] | "[anchor]" | Related guide |
| CTA at end | [URL] | "[anchor]" | User journey |

**Page: [URL 2]**
[Continue for each page...]

### Priority Link Additions

**High Impact Links** (add these first):

1. **From**: [Source URL]
   **To**: [Target URL]
   **Anchor**: "[anchor text]"
   **Why**: [reason - e.g., "Target page needs authority boost"]
   **Where to add**: [specific location in content]

2. **From**: [Source URL]
   **To**: [Target URL]
   [etc.]
```

---

## Step 6: Optimize Navigation and Footer Links

```markdown
## Site-Wide Link Optimization

### Current Navigation Analysis

**Main Navigation**:
- Links present: [list]
- Missing important pages: [list]
- Too many links: [Yes/No]

**Footer Navigation**:
- Links present: [list]
- SEO value: [assessment]

### Navigation Recommendations

| Element | Current | Recommended | Reason |
|---------|---------|-------------|--------|
| Main nav | [X] links | [Y] links | [reason] |
| Footer | [X] links | [Y] links | [reason] |
| Sidebar | [status] | [recommendation] | [reason] |
| Breadcrumbs | [status] | [recommendation] | [reason] |

### Pages to Add to Navigation

1. [Page] - Add to [location] because [reason]
2. [Page] - Add to [location] because [reason]

### Pages to Remove from Navigation

1. [Page] - Move to [footer/remove] because [reason]
```

---

## Step 7: Generate Link Implementation Plan

```markdown
# Internal Linking Optimization Plan

**Site**: [domain]
**Analysis Date**: [date]

## Executive Summary

- Total link opportunities found: [X]
- Orphan pages to fix: [X]
- Estimated traffic impact: [+X%]
- Priority actions: [X]

## Current State

| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| Avg links per page | [X] | [X] | [X] |
| Orphan pages | [X] | 0 | [X] |
| Over-optimized anchors | [X]% | <10% | [X]% |
| Topic cluster coverage | [X]% | 100% | [X]% |

## Priority Actions

### Phase 1: Critical Fixes (Week 1)

**Fix Orphan Pages**:
- [ ] [URL] - Add links from [X] pages
- [ ] [URL] - Add links from [X] pages

**High-Value Link Additions**:
- [ ] Link [Page A] to [Page B] with "[anchor]"
- [ ] Link [Page A] to [Page C] with "[anchor]"

### Phase 2: Topic Clusters (Week 2-3)

**Cluster 1: [Topic]**
- [ ] Ensure pillar links to all [X] cluster articles
- [ ] Add [X] cross-links between cluster articles

**Cluster 2: [Topic]**
- [ ] [Tasks]

### Phase 3: Optimization (Week 4+)

**Anchor Text Diversity**:
- [ ] Vary anchors for [Page] - currently [X]% exact match
- [ ] [Additional tasks]

**Navigation Updates**:
- [ ] Add [Page] to main navigation
- [ ] Update footer links

## Implementation Guide

### Adding Internal Links

Best practices:
1. Add links contextually within content
2. Use descriptive anchor text (not "click here")
3. Link to relevant, helpful pages
4. Aim for 3-10 internal links per 1,000 words
5. Vary anchor text for the same target

### Anchor Text Guidelines

| Type | Example | Usage |
|------|---------|-------|
| Exact match | "keyword research" | 10-20% |
| Partial match | "tips for keyword research" | 30-40% |
| Branded | "Brand's guide to..." | 10-20% |
| Natural | "this article", "learn more" | 20-30% |

## Tracking Success

Monitor these metrics weekly:
- [ ] Rankings for target keywords
- [ ] Traffic to previously orphan pages
- [ ] Crawl stats in ~~search console
- [ ] Internal link distribution changes
```
