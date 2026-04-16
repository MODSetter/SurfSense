# Topic Cluster Templates

Planning worksheets, architecture patterns, and measurement frameworks for building topic clusters that establish topical authority and drive organic traffic.

## Overview

A topic cluster is a group of interlinked content pieces organized around a central pillar page. The pillar covers a broad topic comprehensively, while cluster pages dive deep into specific subtopics. Internal links bind the cluster together, signaling topical authority to search engines and AI systems.

---

## Topic Cluster Planning Worksheet

### Step 1: Define the Pillar Topic

Use this template to evaluate whether a topic deserves a full cluster:

| Field | Your Input |
|-------|-----------|
| **Pillar Topic** | [Broad topic name] |
| **Pillar Keyword** | [Head keyword, typically 1-3 words] |
| **Monthly Search Volume** | [Volume] |
| **Keyword Difficulty** | [KD score] |
| **Business Relevance** | [1-5 scale: how core is this to your product/service?] |
| **Current Ranking** | [Your current position, or "Not ranking"] |
| **Competitor Coverage** | [How many competitors have pillar content on this?] |
| **Estimated Cluster Size** | [How many subtopics can you identify?] |
| **Content Assets Available** | [Existing content you can repurpose or link] |

**Pillar viability checklist:**
- [ ] At least 8-12 subtopics can be identified
- [ ] Combined cluster keyword volume exceeds 5,000/month
- [ ] Topic is directly relevant to your product or service
- [ ] You can provide unique expertise or data on this topic
- [ ] Competitors have not yet built a dominant cluster

### Step 2: Map Cluster Subtopics

| # | Subtopic | Target Keyword | Volume | KD | Intent | Content Format | Status |
|---|---------|---------------|--------|-----|--------|---------------|--------|
| 1 | [Subtopic name] | [Long-tail keyword] | [Vol] | [KD] | [I/N/C/T] | [Guide/Tutorial/List/etc.] | [Idea/Draft/Published] |
| 2 | [Subtopic name] | [Long-tail keyword] | [Vol] | [KD] | [I/N/C/T] | [Guide/Tutorial/List/etc.] | [Idea/Draft/Published] |
| 3 | [Subtopic name] | [Long-tail keyword] | [Vol] | [KD] | [I/N/C/T] | [Guide/Tutorial/List/etc.] | [Idea/Draft/Published] |
| 4 | [Subtopic name] | [Long-tail keyword] | [Vol] | [KD] | [I/N/C/T] | [Guide/Tutorial/List/etc.] | [Idea/Draft/Published] |
| 5 | [Subtopic name] | [Long-tail keyword] | [Vol] | [KD] | [I/N/C/T] | [Guide/Tutorial/List/etc.] | [Idea/Draft/Published] |
| 6 | [Subtopic name] | [Long-tail keyword] | [Vol] | [KD] | [I/N/C/T] | [Guide/Tutorial/List/etc.] | [Idea/Draft/Published] |
| 7 | [Subtopic name] | [Long-tail keyword] | [Vol] | [KD] | [I/N/C/T] | [Guide/Tutorial/List/etc.] | [Idea/Draft/Published] |
| 8 | [Subtopic name] | [Long-tail keyword] | [Vol] | [KD] | [I/N/C/T] | [Guide/Tutorial/List/etc.] | [Idea/Draft/Published] |

### Step 3: Define Internal Linking Map

| Source Page | Links To | Anchor Text Strategy |
|------------|---------|---------------------|
| Pillar | Cluster 1, 2, 3... (all) | Descriptive, keyword-relevant anchors |
| Cluster 1 | Pillar + Cluster 2, 3 | Natural contextual links |
| Cluster 2 | Pillar + Cluster 1, 4 | Natural contextual links |
| Cluster 3 | Pillar + Cluster 1 | Natural contextual links |

**Linking rules:**
- Every cluster page MUST link to the pillar page
- The pillar page MUST link to every cluster page
- Cluster pages SHOULD link to 2-3 related cluster pages where contextually relevant
- Use descriptive anchor text (not "click here" or bare URLs)
- Link placement should be within body content, not just in a footer list

---

## Hub-and-Spoke Architecture Patterns

### Pattern 1: Classic Hub-Spoke (Best for Educational Topics)

```
                         ┌──────────────────┐
                    ┌────│ What is [Topic]?  │
                    │    └──────────────────┘
                    │    ┌──────────────────┐
                    ├────│ [Topic] Benefits  │
                    │    └──────────────────┘
┌───────────────┐   │    ┌──────────────────┐
│    PILLAR:    │───┼────│ [Topic] Examples  │
│ Complete      │   │    └──────────────────┘
│ Guide to      │   │    ┌──────────────────┐
│ [Topic]       │   ├────│ [Topic] Tools     │
└───────────────┘   │    └──────────────────┘
                    │    ┌──────────────────┐
                    ├────│ [Topic] Mistakes  │
                    │    └──────────────────┘
                    │    ┌──────────────────┐
                    └────│ [Topic] Checklist │
                         └──────────────────┘
```

**Best for:** Broad educational topics where subtopics don't overlap much.
**Example:** "Content Marketing" pillar with spokes for strategy, types, examples, tools, metrics, mistakes.

### Pattern 2: Layered Cluster (Best for Technical Topics)

```
                    ┌─────────────────────────────┐
               ┌────│ BEGINNER CLUSTER             │
               │    │ - Getting Started            │
               │    │ - Basic Concepts             │
               │    │ - First Steps Tutorial       │
               │    └─────────────────────────────┘
┌──────────┐   │    ┌─────────────────────────────┐
│ PILLAR:  │───┼────│ INTERMEDIATE CLUSTER         │
│ Complete │   │    │ - Advanced Techniques        │
│ Guide    │   │    │ - Common Patterns            │
└──────────┘   │    │ - Optimization Strategies    │
               │    └─────────────────────────────┘
               │    ┌─────────────────────────────┐
               └────│ ADVANCED CLUSTER             │
                    │ - Expert Strategies          │
                    │ - Edge Cases                 │
                    │ - Integration Guides         │
                    └─────────────────────────────┘
```

**Best for:** Topics with clear skill progressions (programming, technical SEO, data analysis).
**Example:** "Technical SEO" pillar with beginner (crawling basics), intermediate (JavaScript rendering), advanced (log file analysis) layers.

### Pattern 3: Use-Case Cluster (Best for Product/Service Topics)

```
                    ┌──────────────────────┐
               ┌────│ [Topic] for SMBs     │
               │    └──────────────────────┘
               │    ┌──────────────────────┐
┌──────────┐   ├────│ [Topic] for Enterprise│
│ PILLAR:  │───┤    └──────────────────────┘
│ [Topic]  │   │    ┌──────────────────────┐
│ Guide    │   ├────│ [Topic] for Agencies  │
└──────────┘   │    └──────────────────────┘
               │    ┌──────────────────────┐
               ├────│ [Topic] for Ecommerce │
               │    └──────────────────────┘
               │    ┌──────────────────────┐
               └────│ [Topic] for SaaS      │
                    └──────────────────────┘
```

**Best for:** Products/services with distinct audience segments.
**Example:** "SEO Strategy" pillar with spokes for different business types (ecommerce SEO, SaaS SEO, local SEO, B2B SEO).

### Pattern 4: Process Cluster (Best for How-To Topics)

```
┌──────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ PILLAR:  │────→│ Step 1:  │────→│ Step 2:  │────→│ Step 3:  │────→│ Step 4:  │
│ How to   │     │ Research │     │ Plan     │     │ Execute  │     │ Measure  │
│ [Process]│     └─────────┘     └─────────┘     └─────────┘     └─────────┘
└──────────┘          │               │               │               │
                 ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
                 │Sub-guide │    │Template  │    │Tutorial  │    │Dashboard │
                 │  1a      │    │  2a      │    │  3a      │    │  Guide   │
                 └─────────┘    └─────────┘    └─────────┘    └─────────┘
```

**Best for:** Multi-step processes where each step is complex enough for its own article.
**Example:** "Link Building" pillar with sequential steps (prospecting, outreach, content creation, tracking).

---

## Internal Linking Patterns Within Clusters

### Linking Density Guidelines

| Cluster Size | Min Links Per Cluster Page | Max Links Per Cluster Page | Pillar Link Density |
|-------------|--------------------------|--------------------------|-------------------|
| 5-8 pages | 2-3 internal links | 5-6 internal links | Link to every cluster page |
| 9-15 pages | 3-4 internal links | 6-8 internal links | Link to every cluster page |
| 16+ pages | 4-5 internal links | 8-10 internal links | Link to top cluster pages, categorize rest |

### Anchor Text Strategy

| Link Type | Anchor Text Approach | Example |
|-----------|---------------------|---------|
| Cluster → Pillar | Broad keyword or branded | "our complete guide to keyword research" |
| Pillar → Cluster | Specific keyword for that cluster page | "learn about long-tail keyword strategies" |
| Cluster → Cluster | Contextual, conversational | "this connects to how you assess keyword difficulty" |

### Linking Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Fix |
|-------------|-------------|-----|
| Footer-only links to cluster pages | Low link equity, poor UX | Move links into body content |
| Generic anchors ("click here", "read more") | No keyword signal | Use descriptive, keyword-relevant anchors |
| Orphan cluster pages (no inbound links) | Search engines can't discover/value them | Add contextual links from pillar and related clusters |
| Over-linking (20+ internal links per page) | Dilutes link equity, feels spammy | Keep to 5-10 relevant internal links |
| Linking only to pillar (ignoring sibling clusters) | Misses cross-cluster relevance | Link to 2-3 related sibling pages |

---

## Content Calendar Integration

### Cluster Build Sequence

The order you publish cluster content matters. Follow this sequence for maximum impact:

| Phase | What to Publish | Why This Order |
|-------|----------------|---------------|
| **Phase 1: Pillar** | Publish the pillar page first | Establishes the hub; cluster pages need something to link to |
| **Phase 2: Quick-win clusters** | Publish 3-4 lowest-difficulty cluster pages | Build early traffic and indexing momentum |
| **Phase 3: High-value clusters** | Publish highest-volume cluster pages | Leverage pillar authority for competitive terms |
| **Phase 4: Long-tail clusters** | Publish remaining niche subtopics | Fill coverage gaps, capture long-tail traffic |
| **Phase 5: Update cycle** | Refresh pillar with new links; update outdated clusters | Maintain freshness signals |

### Sample Content Calendar for One Cluster

| Week | Content Piece | Type | Target Keyword | Word Count | Dependencies |
|------|--------------|------|---------------|-----------|-------------|
| 1 | Complete Guide to [Pillar Topic] | Pillar | [Head keyword] | 3,500-5,000 | None |
| 2 | What is [Subtopic A]? | Cluster | [Long-tail A] | 1,500-2,000 | Pillar published |
| 3 | How to [Subtopic B] | Cluster | [Long-tail B] | 2,000-2,500 | Pillar published |
| 4 | [Subtopic C] vs [Subtopic D] | Cluster | [Long-tail C] | 2,000-2,500 | Pillar published |
| 5 | Best [Subtopic E] Tools | Cluster | [Long-tail E] | 2,500-3,000 | Pillar published |
| 6 | [Subtopic F] for Beginners | Cluster | [Long-tail F] | 1,500-2,000 | Pillar published |
| 7 | [Subtopic G] Checklist | Cluster | [Long-tail G] | 1,000-1,500 | Pillar published |
| 8 | Update Pillar + add all internal links | Update | -- | -- | All clusters published |

### Publishing Cadence Recommendations

| Team Size | Cluster Build Time | Recommended Cadence |
|-----------|-------------------|-------------------|
| Solo content creator | 6-8 weeks per cluster | 1 cluster per quarter |
| Small team (2-3 writers) | 3-4 weeks per cluster | 1 cluster per month |
| Content team (4-6 writers) | 2-3 weeks per cluster | 2 clusters per month |
| Large team (7+ writers) | 1-2 weeks per cluster | 1 cluster per week |

---

## Cluster Performance Measurement Framework

### Key Metrics by Level

#### Cluster-Level Metrics

| Metric | What It Measures | Target | How to Track |
|--------|-----------------|--------|-------------|
| Total cluster traffic | Aggregate organic visits to all pages in cluster | Growing month-over-month | Analytics: filter by URL folder/tag |
| Keyword coverage | Number of keywords cluster ranks for | 50+ keywords per mature cluster | SEO tool: filter by cluster URLs |
| Average position | Mean ranking across all cluster keywords | Improving trend toward top 10 | SEO tool: average position report |
| Internal link equity | PageRank flow within cluster | Pillar has highest internal links | Site audit tool: internal link report |
| Cluster completeness | Percentage of planned subtopics published | 100% within planned timeframe | Content calendar tracking |

#### Page-Level Metrics (Per Cluster Page)

| Metric | Pillar Target | Cluster Page Target |
|--------|-------------|-------------------|
| Organic traffic | Highest in cluster | Proportional to keyword volume |
| Keywords ranking | 50-200+ | 10-50 |
| Backlinks | Attracts most links | Some organic links |
| Avg. time on page | 4-8 minutes | 2-5 minutes |
| Bounce rate | <60% | <70% |
| Internal CTR | High clicks to cluster pages | Clicks to pillar + sibling pages |

### Performance Review Cadence

| Timeframe | What to Review | Action If Underperforming |
|-----------|---------------|--------------------------|
| 2 weeks post-publish | Indexing status, initial impressions | Fix indexing issues, check for crawl errors |
| 1 month post-publish | Early ranking signals, traffic | Optimize titles/metas, add internal links |
| 3 months post-publish | Ranking positions, traffic trends | Content refresh, add missing subtopics, build links |
| 6 months post-publish | Full performance assessment | Major content update or strategic pivot |
| Quarterly (ongoing) | Cluster-level aggregate trends | Identify declining pages, plan refreshes |

### Cluster Health Scorecard

Rate each cluster quarterly on these dimensions:

| Dimension | Score 1 (Poor) | Score 3 (Average) | Score 5 (Excellent) |
|-----------|---------------|-------------------|-------------------|
| Traffic growth | Declining | Flat | Growing 10%+ MoM |
| Keyword coverage | <20 keywords | 20-50 keywords | 50+ keywords |
| Top 10 rankings | 0 keywords in top 10 | 1-5 in top 10 | 5+ in top 10 |
| Content freshness | Not updated in 12+ months | Updated within 6 months | Updated within 3 months |
| Internal linking | Missing links, orphan pages | Basic linking in place | Full cross-linking with relevant anchors |
| Completeness | <50% of subtopics covered | 50-80% covered | 80-100% covered |

**Cluster Health Score** = Average of all dimension scores

| Score Range | Health Status | Action |
|------------|--------------|--------|
| 4.0-5.0 | Healthy | Maintain cadence, expand to adjacent clusters |
| 3.0-3.9 | Needs attention | Refresh outdated content, fill subtopic gaps |
| 2.0-2.9 | At risk | Major content update, link building campaign |
| 1.0-1.9 | Failing | Strategic review -- consider merging, rewriting, or retiring |
