# SERP Analysis — Analysis Templates

Templates for each step of the SERP analysis workflow. Use these to structure your output.

## SERP Composition Template

```markdown
## SERP Analysis: "[keyword]"

**Search Details**
- Keyword: [keyword]
- Location: [location]
- Device: [mobile/desktop]
- Date: [date]

### SERP Layout Overview

```
┌─────────────────────────────────────────┐
│ [AI Overview / SGE] (if present)        │
├─────────────────────────────────────────┤
│ [Ads] - [X] ads above fold              │
├─────────────────────────────────────────┤
│ [Featured Snippet] (if present)         │
├─────────────────────────────────────────┤
│ [Organic Result #1]                     │
│ [Organic Result #2]                     │
│ [People Also Ask] (if present)          │
│ [Organic Result #3]                     │
│ ...                                     │
├─────────────────────────────────────────┤
│ [Related Searches]                      │
└─────────────────────────────────────────┘
```

### SERP Features Present

| Feature | Present | Position | Opportunity |
|---------|---------|----------|-------------|
| AI Overview | Yes/No | Top | [analysis] |
| Featured Snippet | Yes/No | [pos] | [analysis] |
| People Also Ask | Yes/No | [pos] | [analysis] |
| Knowledge Panel | Yes/No | Right | [analysis] |
| Image Pack | Yes/No | [pos] | [analysis] |
| Video Results | Yes/No | [pos] | [analysis] |
| Local Pack | Yes/No | [pos] | [analysis] |
| Shopping Results | Yes/No | [pos] | [analysis] |
| News Results | Yes/No | [pos] | [analysis] |
| Sitelinks | Yes/No | [pos] | [analysis] |
```

## Top Results Analysis Template

```markdown
### Top 10 Organic Results Analysis

#### Position #1: [Title]

**URL**: [url]
**Domain**: [domain]
**Domain Authority**: [DA]

**Content Analysis**:
- Type: [Blog/Product/Guide/etc.]
- Word Count: [X] words
- Publish Date: [date]
- Last Updated: [date]

**On-Page Factors**:
- Title: [exact title]
- Title contains keyword: Yes/No
- Meta description: [description]
- H1: [heading]
- URL structure: [clean/keyword-rich/etc.]

**Content Structure**:
- Headings (H2s): [list key sections]
- Media: [X] images, [X] videos
- Tables/Lists: Yes/No
- FAQ section: Yes/No

**Estimated Metrics**:
- Page backlinks: [X]
- Referring domains: [X]
- Social shares: [X]

**Why It Ranks #1**:
1. [Factor 1]
2. [Factor 2]
3. [Factor 3]

[Repeat for positions #2-10]
```

## Ranking Patterns Template

```markdown
### Ranking Patterns Analysis

**Common Characteristics of Top 5 Results**:

| Factor | Avg/Common Value | Importance |
|--------|-----------------|------------|
| Word Count | [X] words | High/Med/Low |
| Domain Authority | [X] | High/Med/Low |
| Page Backlinks | [X] | High/Med/Low |
| Content Freshness | [timeframe] | High/Med/Low |
| HTTPS | [X]% | High/Med/Low |
| Mobile Optimized | [X]% | High/Med/Low |

**Content Format Distribution**:
- How-to guides: [X]/10
- Listicles: [X]/10
- In-depth articles: [X]/10
- Product pages: [X]/10
- Other: [X]/10

**Domain Type Distribution**:
- Brand/Company sites: [X]/10
- Media/News sites: [X]/10
- Niche blogs: [X]/10
- Aggregators: [X]/10

**Key Success Factors Identified**:

1. **[Factor 1]**: [Explanation + evidence]
2. **[Factor 2]**: [Explanation + evidence]
3. **[Factor 3]**: [Explanation + evidence]
```

## SERP Features Analysis Template

```markdown
### Featured Snippet Analysis

**Current Snippet Holder**: [URL]
**Snippet Type**: [Paragraph/List/Table/Video]
**Snippet Content**:
> [Exact text/description of snippet]

**How to Win This Snippet**:
1. [Strategy based on current snippet]
2. [Content format recommendation]
3. [Structure recommendation]

---

### People Also Ask (PAA) Analysis

**Questions Appearing**:
1. [Question 1] → Currently answered by: [URL]
2. [Question 2] → Currently answered by: [URL]
3. [Question 3] → Currently answered by: [URL]
4. [Question 4] → Currently answered by: [URL]

**PAA Optimization Strategy**:
- Include these questions as H2/H3 headings
- Provide direct, concise answers (40-60 words)
- Use FAQ schema markup

---

### AI Overview Analysis

**AI Overview Present**: Yes/No
**AI Overview Type**: [Summary/List/Comparison/etc.]

**Sources Cited in AI Overview**:
1. [Source 1] - [Why cited]
2. [Source 2] - [Why cited]
3. [Source 3] - [Why cited]

**AI Overview Content Patterns**:
- Pulls definitions from: [source type]
- Lists information as: [format]
- Cites statistics from: [source type]

**How to Get Cited in AI Overview**:
1. [Specific recommendation]
2. [Specific recommendation]
3. [Specific recommendation]
```

## Search Intent Template

```markdown
### Search Intent Analysis

**Primary Intent**: [Informational/Commercial/Transactional/Navigational]

**Evidence**:
- SERP features suggest: [analysis]
- Top results are: [content types]
- User likely wants: [description]

**Intent Breakdown**:
- Informational signals: [X]%
- Commercial signals: [X]%
- Transactional signals: [X]%

**Content Format Implication**:
Based on intent, your content should:
- Format: [recommendation]
- Tone: [recommendation]
- CTA: [recommendation]
```

## Difficulty Assessment Template

```markdown
### Difficulty Assessment

**Overall Difficulty Score**: [X]/100

**Difficulty Factors**:

| Factor | Score | Weight | Impact |
|--------|-------|--------|--------|
| Top 10 Domain Authority | [avg] | 25% | [High/Med/Low] |
| Top 10 Page Authority | [avg] | 20% | [High/Med/Low] |
| Backlinks Required | [est.] | 20% | [High/Med/Low] |
| Content Quality Bar | [rating] | 20% | [High/Med/Low] |
| SERP Stability | [rating] | 15% | [High/Med/Low] |

**Realistic Assessment**:

- **New site (DA <20)**: [Can rank?] [Timeframe]
- **Growing site (DA 20-40)**: [Can rank?] [Timeframe]
- **Established site (DA 40+)**: [Can rank?] [Timeframe]

**Easier Alternatives**:
If too difficult, consider:
- [Alternative keyword 1] - Difficulty: [X]
- [Alternative keyword 2] - Difficulty: [X]
```

## Recommendations Template

```markdown
## SERP Analysis Summary & Recommendations

### Key Findings

1. [Most important finding]
2. [Second important finding]
3. [Third important finding]

### Content Requirements to Rank

To compete for "[keyword]", you need:

**Minimum Requirements**:
- [ ] Word count: [X]+ words
- [ ] Backlinks: [X]+ referring domains
- [ ] Domain Authority: [X]+
- [ ] Content format: [type]
- [ ] Include: [specific elements]

**Differentiators to Win**:
- [ ] [Unique angle from analysis]
- [ ] [Missing element in current results]
- [ ] [SERP feature opportunity]

### SERP Feature Strategy

| Feature | Winnable? | Strategy |
|---------|-----------|----------|
| Featured Snippet | Yes/No | [strategy] |
| PAA | Yes/No | [strategy] |
| AI Overview | Yes/No | [strategy] |

### Recommended Content Outline

Based on SERP analysis:

```
Title: [Optimized title]

H1: [Main heading]

[Introduction - address intent immediately]

H2: [Section based on PAA/top results]
H2: [Section based on PAA/top results]
H2: [Section based on PAA/top results]

[FAQ section for PAA optimization]

[Conclusion with CTA]
```

### Next Steps

1. [Immediate action]
2. [Content creation action]
3. [Optimization action]
```
