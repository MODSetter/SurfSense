# Backlink Analysis Output Templates

Detailed output templates for each step of the backlink analysis workflow. Use these templates when generating analysis deliverables.

---

## 1. Profile Overview Template

```markdown
## Backlink Profile Overview

**Domain**: [domain]
**Analysis Date**: [date]

### Key Metrics

| Metric | Value | Industry Avg | Status |
|--------|-------|--------------|--------|
| Total Backlinks | [X] | [Y] | [Above/Below avg] |
| Referring Domains | [X] | [Y] | [status] |
| Domain Authority | [X] | [Y] | [status] |
| Domain Rating | [X] | [Y] | [status] |
| Dofollow Links | [X] ([Y]%) | [Z]% | [status] |
| Nofollow Links | [X] ([Y]%) | [Z]% | [status] |

### Link Velocity

| Period | New Links | Lost Links | Net Change |
|--------|-----------|------------|------------|
| Last 30 days | [X] | [Y] | [+/-Z] |
| Last 90 days | [X] | [Y] | [+/-Z] |
| Last year | [X] | [Y] | [+/-Z] |

### Authority Distribution

```
DA 80-100: [X]%
DA 60-79:  [X]%
DA 40-59:  [X]%
DA 20-39:  [X]%
DA 0-19:   [X]%
```

**Profile Health Score**: [X]/100
```

---

## 2. Link Quality Analysis Template

```markdown
## Link Quality Analysis

### Top Quality Backlinks

| Source Domain | DA | Link Type | Anchor | Target Page |
|---------------|-----|-----------|--------|-------------|
| [domain 1] | [DA] | Editorial | [anchor] | [page] |
| [domain 2] | [DA] | Guest Post | [anchor] | [page] |
| [domain 3] | [DA] | Resource | [anchor] | [page] |

### Link Type Distribution

| Type | Count | Percentage | Assessment |
|------|-------|------------|------------|
| Editorial | [X] | [Y]% | High quality |
| Guest posts | [X] | [Y]% | Good |
| Resource pages | [X] | [Y]% | Good |
| Directory | [X] | [Y]% | Moderate |
| Forum/Comments | [X] | [Y]% | Low quality |
| Sponsored/Paid | [X] | [Y]% | Risky |

### Anchor Text Analysis

| Anchor Type | Count | Percentage | Status |
|-------------|-------|------------|--------|
| Brand name | [X] | [Y]% | Natural |
| Exact match | [X] | [Y]% | [Warning if >30%] |
| Partial match | [X] | [Y]% | Natural |
| URL/Naked | [X] | [Y]% | Natural |
| Generic | [X] | [Y]% | Natural |

**Top Anchor Texts**:
1. "[anchor 1]" - [X] links
2. "[anchor 2]" - [X] links
3. "[anchor 3]" - [X] links

### Geographic Distribution

| Country | Links | Percentage |
|---------|-------|------------|
| [Country 1] | [X] | [Y]% |
| [Country 2] | [X] | [Y]% |
| [Country 3] | [X] | [Y]% |
```

---

## 3. Toxic Link Analysis Template

```markdown
## Toxic Link Analysis

### Risk Summary

**Toxic Score**: [X]/100
**High Risk Links**: [X]
**Medium Risk Links**: [X]
**Action Required**: [Yes/No]

### Toxic Link Indicators

| Risk Type | Count | Examples |
|-----------|-------|----------|
| Spammy domains | [X] | [domains] |
| Link farms | [X] | [domains] |
| PBN suspected | [X] | [domains] |
| Irrelevant sites | [X] | [domains] |
| Foreign language spam | [X] | [domains] |
| Penalized domains | [X] | [domains] |

### High-Risk Links to Review

| Source Domain | Risk Score | Issue | Recommendation |
|---------------|------------|-------|----------------|
| [domain 1] | 95/100 | Link farm | Disavow |
| [domain 2] | 85/100 | Spam site | Disavow |
| [domain 3] | 72/100 | PBN | Investigate |

### Disavow Recommendations

**Domains to disavow** ([X] total):
```
domain:[spam-site-1.com]
domain:[spam-site-2.com]
domain:[link-farm.com]
```

**Individual URLs to disavow** ([X] total):
```
[specific-url-1]
[specific-url-2]
```
```

---

## 4. Competitive Backlink Analysis Template

```markdown
## Competitive Backlink Analysis

### Profile Comparison

| Metric | You | Competitor 1 | Competitor 2 | Competitor 3 |
|--------|-----|--------------|--------------|--------------|
| Referring Domains | [X] | [X] | [X] | [X] |
| Domain Authority | [X] | [X] | [X] | [X] |
| Domain Rating | [X] | [X] | [X] | [X] |
| Link Velocity (30d) | [X] | [X] | [X] | [X] |
| Avg Link DA | [X] | [X] | [X] | [X] |

### Unique Referring Domains

**Links only you have**: [X] domains
**Links competitors share**: [X] domains
**Links competitors have, you don't**: [X] domains -- Opportunity

### Link Intersection Analysis

**Sites linking to competitors but not you**:

| Domain | DA | Links to Comp 1 | Comp 2 | Comp 3 | Opportunity |
|--------|-----|-----------------|--------|--------|-------------|
| [domain 1] | [DA] | Yes | Yes | Yes | High - All competitors |
| [domain 2] | [DA] | Yes | Yes | No | High - 2 competitors |
| [domain 3] | [DA] | Yes | No | No | Medium - 1 competitor |

### Content Getting Most Links (Competitor Analysis)

| Competitor | Content | Backlinks | Content Type |
|------------|---------|-----------|--------------|
| [Comp 1] | [Title/URL] | [X] | [Type] |
| [Comp 2] | [Title/URL] | [X] | [Type] |
| [Comp 3] | [Title/URL] | [X] | [Type] |

**Insight**: [What content types attract most links in this niche]
```

---

## 5. Link Building Opportunities Template

```markdown
## Link Building Opportunities

### High-Priority Opportunities

#### 1. Link Intersection Prospects

Sites linking to multiple competitors but not you:

| Domain | DA | Why Link | Contact Approach |
|--------|-----|----------|------------------|
| [domain 1] | [DA] | [resource page about X] | Suggest your resource |
| [domain 2] | [DA] | [links to similar tools] | Pitch your tool |
| [domain 3] | [DA] | [industry roundup] | Request inclusion |

#### 2. Broken Link Opportunities

| Source Page | Broken Link | Suggested Replacement |
|-------------|-------------|----------------------|
| [URL] | [broken URL] | [your relevant page] |

#### 3. Unlinked Mentions

| Site | Mention | Your Page to Link |
|------|---------|-------------------|
| [domain] | Mentioned your brand | [homepage] |
| [domain] | Referenced your data | [research page] |

#### 4. Resource Page Opportunities

| Resource Page | Topic | Your Relevant Content |
|---------------|-------|----------------------|
| [URL] | [topic] | [your content] |

#### 5. Guest Post Prospects

| Site | DA | Topic Fit | Contact |
|------|-----|-----------|---------|
| [domain] | [DA] | [relevance] | [contact info/page] |

### Link Building Priority Matrix

| Opportunity Type | Effort | Impact | Priority |
|------------------|--------|--------|----------|
| Link intersection | Medium | High | Highest |
| Broken links | Low | Medium | High |
| Unlinked mentions | Low | Medium | High |
| Resource pages | Medium | High | High |
| Guest posts | High | High | Medium |
```

---

## 6. Link Change Tracking Template

```markdown
## Link Change Tracking

### New Links (Last 30 Days)

| Source | DA | Type | Anchor | Date |
|--------|-----|------|--------|------|
| [domain 1] | [DA] | [type] | [anchor] | [date] |

**Total new links**: [X]
**Average DA of new links**: [X]
**Best new link**: [domain] (DA [X])

### Lost Links (Last 30 Days)

| Source | DA | Reason | Action |
|--------|-----|--------|--------|
| [domain 1] | [DA] | Page removed | Reach out |
| [domain 2] | [DA] | Link removed | Investigate |

**Total lost links**: [X]
**Net change**: [+/-X]

### Links to Recover

| Lost Link | Value | Recovery Strategy |
|-----------|-------|-------------------|
| [domain 1] | High | Contact webmaster |
| [domain 2] | High | Update content they linked to |
```

---

## 7. Backlink Report Template

```markdown
# Backlink Analysis Report

**Domain**: [domain]
**Report Date**: [date]
**Period Analyzed**: [period]

## Executive Summary

Your backlink profile is [healthy/needs attention/concerning].

**Key Stats**:
- Referring domains: [X] ([+/-Y] vs last month)
- Average link authority: [X] DA
- Link velocity: [X] new links/month
- Toxic link percentage: [X]%

## Profile Strengths

1. [Strength 1]
2. [Strength 2]
3. [Strength 3]

## Areas of Concern

1. [Concern 1]
2. [Concern 2]

## Opportunities Identified

| Opportunity | Potential Links | Effort | Priority |
|-------------|-----------------|--------|----------|
| Link intersection | [X] sites | Medium | High |
| Broken links | [X] sites | Low | High |
| Resource pages | [X] sites | Medium | Medium |

## Competitive Position

Your referring domains rank #[X] among [Y] competitors.

| Rank | Domain | Referring Domains |
|------|--------|-------------------|
| 1 | [domain] | [X] |
| 2 | [domain] | [X] |
| 3 | [domain] | [X] |

## Recommended Actions

### Immediate (This Week)
- [ ] Disavow [X] toxic links identified
- [ ] Reach out to [X] unlinked mentions

### Short-term (This Month)
- [ ] Pursue [X] link intersection opportunities
- [ ] Fix [X] broken link opportunities
- [ ] Recover [X] recently lost links

### Long-term (This Quarter)
- [ ] Create linkable asset targeting [topic]
- [ ] Launch guest posting campaign
- [ ] Build [X] resource page links

## KPIs to Track

| Metric | Current | 3-Month Target |
|--------|---------|----------------|
| Referring domains | [X] | [Y] |
| Average DA of new links | [X] | [Y] |
| Link velocity | [X]/mo | [Y]/mo |
| Toxic link % | [X]% | <5% |
```
