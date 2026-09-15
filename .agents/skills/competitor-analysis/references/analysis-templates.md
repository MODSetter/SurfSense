# Competitor Analysis — Analysis Templates

Templates for each step of the competitor analysis workflow. Use these to structure your output.

## Competitor Profile Template

```markdown
## Competitor Profile: [Name]

**Basic Info**
- URL: [website]
- Domain Age: [years]
- Estimated Traffic: [monthly visits]
- Domain Authority/Rating: [score]

**Business Model**
- Type: [SaaS/E-commerce/Content/etc.]
- Target Audience: [description]
- Key Offerings: [products/services]
```

## Keyword Analysis Template

```markdown
### Keyword Analysis: [Competitor]

**Total Keywords Ranking**: [X]
**Keywords in Top 10**: [X]
**Keywords in Top 3**: [X]

#### Top Performing Keywords

| Keyword | Position | Volume | Traffic Est. | Page |
|---------|----------|--------|--------------|------|
| [kw 1] | [pos] | [vol] | [traffic] | [url] |
| [kw 2] | [pos] | [vol] | [traffic] | [url] |

#### Keyword Distribution by Intent

- Informational: [X]% ([keywords])
- Commercial: [X]% ([keywords])
- Transactional: [X]% ([keywords])
- Navigational: [X]% ([keywords])

#### Keyword Gaps (They rank, you don't)

| Keyword | Their Position | Volume | Opportunity |
|---------|----------------|--------|-------------|
| [kw 1] | [pos] | [vol] | [analysis] |
```

## Content Analysis Template

```markdown
### Content Analysis: [Competitor]

**Content Volume**
- Total Pages: [X]
- Blog Posts: [X]
- Landing Pages: [X]
- Resource Pages: [X]

**Content Performance**

#### Top Performing Content

| Title | URL | Est. Traffic | Keywords | Backlinks |
|-------|-----|--------------|----------|-----------|
| [title 1] | [url] | [traffic] | [X] | [X] |

**Content Patterns**

- Average word count: [X] words
- Publishing frequency: [X] posts/month
- Content formats used:
  - Blog posts: [X]%
  - Guides/tutorials: [X]%
  - Case studies: [X]%
  - Tools/calculators: [X]%
  - Videos: [X]%

**Content Themes**

| Theme | # Articles | Combined Traffic |
|-------|------------|------------------|
| [theme 1] | [X] | [traffic] |
| [theme 2] | [X] | [traffic] |

**What Makes Their Content Successful**

1. [Success factor 1 with example]
2. [Success factor 2 with example]
3. [Success factor 3 with example]
```

## Backlink Analysis Template

```markdown
### Backlink Analysis: [Competitor]

**Overview**
- Total Backlinks: [X]
- Referring Domains: [X]
- Domain Rating: [X]

**Link Quality Distribution**
- High Authority (DR 70+): [X]%
- Medium Authority (DR 30-69): [X]%
- Low Authority (DR <30): [X]%

**Top Linking Domains**

| Domain | DR | Link Type | Target Page |
|--------|-----|-----------|-------------|
| [domain 1] | [DR] | [type] | [page] |

**Link Acquisition Patterns**

- Guest posts: [X]%
- Editorial/organic: [X]%
- Resource pages: [X]%
- Directories: [X]%
- Other: [X]%

**Linkable Assets (Content attracting links)**

| Asset | Type | Backlinks | Why It Works |
|-------|------|-----------|--------------|
| [asset 1] | [type] | [X] | [reason] |
```

## Technical SEO Assessment Template

```markdown
### Technical Analysis: [Competitor]

**Site Performance**
- Core Web Vitals: [Pass/Fail]
- LCP: [X]s
- FID: [X]ms
- CLS: [X]
- Mobile-friendly: [Yes/No]

**Site Structure**
- Site architecture depth: [X] levels
- Internal linking quality: [Rating]
- URL structure: [Clean/Messy]
- Sitemap present: [Yes/No]

**Technical Strengths**
1. [Strength 1]
2. [Strength 2]

**Technical Weaknesses**
1. [Weakness 1]
2. [Weakness 2]
```

## GEO/AI Citation Analysis Template

```markdown
### GEO Analysis: [Competitor]

**AI Visibility Assessment**

Test competitor content in AI systems for relevant queries:

| Query | AI Mentions Competitor? | What's Cited | Why |
|-------|------------------------|--------------|-----|
| [query 1] | Yes/No | [content] | [reason] |
| [query 2] | Yes/No | [content] | [reason] |

**GEO Strategies Observed**

1. **Clear Definitions**
   - Example: [quote from their content]
   - Effectiveness: [rating]

2. **Quotable Statistics**
   - Example: [quote from their content]
   - Effectiveness: [rating]

3. **Q&A Format Content**
   - Examples found: [X] pages
   - Topics covered: [list]

4. **Authority Signals**
   - Expert authorship: [Yes/No]
   - Citations to sources: [Yes/No]
   - Original research: [Yes/No]

**GEO Opportunities They're Missing**

| Topic | Why Missing | Your Opportunity |
|-------|-------------|------------------|
| [topic 1] | [reason] | [action] |
```

## Synthesis Report Template

```markdown
# Competitive Analysis Report

**Analysis Date**: [Date]
**Competitors Analyzed**: [List]
**Your Site**: [URL]

## Executive Summary

[2-3 paragraph overview of key findings and recommendations]

## Competitive Landscape

| Metric | You | Competitor 1 | Competitor 2 | Competitor 3 |
|--------|-----|--------------|--------------|--------------|
| Domain Authority | [X] | [X] | [X] | [X] |
| Organic Traffic | [X] | [X] | [X] | [X] |
| Keywords Top 10 | [X] | [X] | [X] | [X] |
| Backlinks | [X] | [X] | [X] | [X] |
| Content Pages | [X] | [X] | [X] | [X] |

**Domain Authority Comparison (Recommended)**

When domain-level comparison is needed, run `domain-authority-auditor` for each competitor to get CITE scores:

| Domain | CITE Score | C (Citation) | I (Identity) | T (Trust) | E (Eminence) | Veto |
|--------|-----------|-------------|-------------|----------|-------------|------|
| Your domain | [score] | [score] | [score] | [score] | [score] | [pass/fail] |
| Competitor 1 | [score] | [score] | [score] | [score] | [score] | [pass/fail] |
| Competitor 2 | [score] | [score] | [score] | [score] | [score] | [pass/fail] |

This reveals domain authority gaps that inform link building and brand strategy beyond keyword-level competition.

## Competitor Strengths to Learn From

### [Competitor 1]
- **Strength**: [description]
- **Why It Works**: [analysis]
- **How to Apply**: [action item]

[Repeat for each competitor]

## Competitor Weaknesses to Exploit

### Gap 1: [Description]
- Who's weak: [competitors]
- Opportunity size: [estimate]
- Recommended action: [specific steps]

[Repeat for each gap]

## Keyword Opportunities

### Keywords to Target (Competitor overlap)
| Keyword | Volume | Avg Position | Best Strategy |
|---------|--------|--------------|---------------|
| [kw] | [vol] | [pos] | [strategy] |

### Untapped Keywords (No competitor coverage)
| Keyword | Volume | Difficulty | Opportunity |
|---------|--------|------------|-------------|
| [kw] | [vol] | [diff] | [description] |

## Content Strategy Recommendations

Based on competitor analysis:

1. **Create**: [Content type] about [topic] because [reason]
2. **Improve**: [Existing content] to match/exceed [competitor content]
3. **Promote**: [Content] to sites like [competitor's link sources]

## Action Plan

### Immediate (This Week)
1. [Action item]
2. [Action item]

### Short-term (This Month)
1. [Action item]
2. [Action item]

### Long-term (This Quarter)
1. [Action item]
2. [Action item]
```
