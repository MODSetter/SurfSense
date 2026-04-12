# CITE Domain Authority Report — Example

Full example audit output for reference. See the [SKILL.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/domain-authority-auditor/SKILL.md) for the complete workflow.

## Example

**User**: "Audit domain authority for cloudhosting.com as a content publisher"

**Output**:

```markdown
## CITE Domain Authority Report

### Overview

- **Domain**: cloudhosting.com
- **Domain Type**: Content Publisher
- **Audit Date**: 2025-02-03
- **CITE Score**: 69.9/100 (Medium)
- **Veto Status**: ✅ No triggers

#### Veto Check (Emergency Brake)

| Veto Item | Status | Action |
|-----------|--------|--------|
| T03: Link-Traffic Coherence | ✅ Pass | Link growth correlates with traffic growth |
| T05: Backlink Profile Uniqueness | ✅ Pass | No PBN patterns detected; diverse link sources |
| T09: Penalty & Deindex History | ✅ Pass | No manual actions; clean penalty history |

### Dimension Scores

| Dimension | Score | Rating | Weight | Weighted |
|-----------|-------|--------|--------|----------|
| C — Citation | 72/100 | Medium | 40% | 28.8 |
| I — Identity | 58/100 | Low | 15% | 8.7 |
| T — Trust | 81/100 | Good | 20% | 16.2 |
| E — Eminence | 65/100 | Medium | 25% | 16.25 |
| **CITE Score** | | | | **69.9/100** |

**Score Calculation**:
- CITE Score = 72 × 0.40 + 58 × 0.15 + 81 × 0.20 + 65 × 0.25 = 69.9

**Rating Scale**: 90-100 Excellent | 75-89 Good | 60-74 Medium | 40-59 Low | 0-39 Poor

### Top 5 Priority Improvements

Sorted by: weight × points lost (highest impact first)

1. **I01 Knowledge Graph Presence** — Create entity entry in Google Knowledge Graph
   - Current: Fail | Potential gain: 1.5 weighted points
   - Action: Create Wikidata entry for CloudHost Inc. with P856 (website), P452 (industry), P571 (inception)

2. **C05 AI Citation Volume** — Increase citations in AI-generated answers
   - Current: Partial | Potential gain: 2.0 weighted points
   - Action: Optimize top 10 pages for GEO; add definitive statements AI can quote directly

3. **I03 Brand SERP Control** — Branded SERP shows only 4 of 10 results from owned properties
   - Current: Partial | Potential gain: 0.75 weighted points
   - Action: Claim Google Business Profile; build out social profiles; create CrunchBase entry

4. **E04 Content Freshness Cadence** — 40% of content is >12 months without update
   - Current: Partial | Potential gain: 1.25 weighted points
   - Action: Establish monthly content refresh schedule; prioritize top 20 traffic pages

5. **I05 Schema.org Completeness** — Organization schema missing sameAs, founder, foundingDate
   - Current: Partial | Potential gain: 0.75 weighted points
   - Action: Add complete Organization schema with sameAs links to Wikidata, LinkedIn, CrunchBase

### Action Plan

#### Quick Wins (< 1 week)
- [ ] Add sameAs, founder, and foundingDate to Organization schema
- [ ] Claim Google Business Profile for branded SERP control

#### Medium Effort (1-4 weeks)
- [ ] Create Wikidata entry with complete properties and references
- [ ] Optimize top 10 pages with GEO-friendly definitive statements
- [ ] Create or complete CrunchBase, LinkedIn company page profiles

#### Strategic (1-3 months)
- [ ] Launch monthly content refresh program targeting stale pages
- [ ] Build topical authority through 3-4 pillar content clusters
- [ ] Pursue digital PR to earn mentions on industry publications (TechCrunch, G2)

### Cross-Reference with CORE-EEAT

| Assessment | Score | Rating |
|-----------|-------|--------|
| CITE (Domain) | 69.9/100 | Medium |
| CORE-EEAT (Content) | Run content-quality-auditor on sample pages | — |

**Diagnosis**: Low CITE + unknown CORE-EEAT → Run `/seo:audit-page` on top 5 landing pages to determine whether to prioritize content quality or domain authority first.

### Recommended Next Steps

- For entity building: run `entity-optimizer` to strengthen I-dimension signals
- For content audit: use `content-quality-auditor` on key pages
- For tracking progress: run `/seo:report` with CITE score trends quarterly
```
