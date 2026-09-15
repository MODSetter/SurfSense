# On-Page SEO Auditor — Output Templates

Detailed output templates for on-page-seo-auditor steps 5-11. Referenced from [SKILL.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/on-page-seo-auditor/SKILL.md).

---

## Step 5: Audit Content Quality

```markdown
## Content Quality Analysis

**Word Count**: [X] words
**Reading Level**: [Grade level]
**Estimated Read Time**: [X] minutes

| Criterion | Status | Notes |
|-----------|--------|-------|
| Sufficient length | ✅/⚠️/❌ | [comparison to ranking content] |
| Comprehensive coverage | ✅/⚠️/❌ | [notes] |
| Unique value/insights | ✅/⚠️/❌ | [notes] |
| Up-to-date information | ✅/⚠️/❌ | [notes] |
| Proper formatting | ✅/⚠️/❌ | [notes] |
| Readability | ✅/⚠️/❌ | [notes] |
| E-E-A-T signals | ✅/⚠️/❌ | [notes] |

**Content Elements Present**:
- [ ] Introduction with keyword
- [ ] Clear sections/structure
- [ ] Bullet points/lists
- [ ] Tables where appropriate
- [ ] Images/visuals
- [ ] Examples/case studies
- [ ] Statistics with sources
- [ ] Expert quotes
- [ ] FAQ section
- [ ] Conclusion with CTA

**Content Score**: [X]/10

**Gaps Identified**:
- [Missing topic/section 1]
- [Missing topic/section 2]

**Recommendations**:
1. [Specific improvement]
2. [Specific improvement]
```

---

## Step 6: Audit Keyword Usage

```markdown
## Keyword Optimization Analysis

**Primary Keyword**: "[keyword]"
**Keyword Density**: [X]%

### Keyword Placement

| Location | Present | Notes |
|----------|---------|-------|
| Title tag | ✅/❌ | Position: [X] |
| Meta description | ✅/❌ | [notes] |
| H1 | ✅/❌ | [notes] |
| First 100 words | ✅/❌ | Word position: [X] |
| H2 headings | ✅/❌ | In [X]/[Y] H2s |
| Body content | ✅/❌ | [X] occurrences |
| URL slug | ✅/❌ | [notes] |
| Image alt text | ✅/❌ | In [X]/[Y] images |
| Conclusion | ✅/❌ | [notes] |

### Secondary Keywords

| Keyword | Occurrences | Status |
|---------|-------------|--------|
| [keyword 1] | [X] | ✅/⚠️/❌ |
| [keyword 2] | [X] | ✅/⚠️/❌ |

### LSI/Related Terms

**Present**: [list of related terms found]
**Missing**: [important related terms not found]

**Keyword Score**: [X]/10

**Issues**:
- [Issue 1]

**Recommendations**:
- [Suggestion 1]
```

---

## Step 7: Audit Internal Links

```markdown
## Internal Linking Analysis

**Total Internal Links**: [X]
**Unique Internal Links**: [X]

| Criterion | Status | Notes |
|-----------|--------|-------|
| Number of internal links | ✅/⚠️/❌ | [X] (recommend 3-5+) |
| Relevant anchor text | ✅/⚠️/❌ | [notes] |
| Links to related content | ✅/⚠️/❌ | [notes] |
| Links to important pages | ✅/⚠️/❌ | [notes] |
| No broken links | ✅/⚠️/❌ | [X] broken found |
| Natural placement | ✅/⚠️/❌ | [notes] |

**Current Internal Links**:
1. "[Anchor text]" → [URL]
2. "[Anchor text]" → [URL]
3. "[Anchor text]" → [URL]

**Internal Linking Score**: [X]/10

**Recommended Additional Links**:
1. Add link to "[Related page]" with anchor "[suggested anchor]"
2. Add link to "[Related page]" with anchor "[suggested anchor]"

**Anchor Text Improvements**:
- Change "[current anchor]" to "[improved anchor]"
```

---

## Step 8: Audit Images

```markdown
## Image Optimization Analysis

**Total Images**: [X]

### Image Audit Table

| Image | Alt Text | File Name | Size | Status |
|-------|----------|-----------|------|--------|
| [img1] | [alt or "missing"] | [filename] | [KB] | ✅/⚠️/❌ |
| [img2] | [alt or "missing"] | [filename] | [KB] | ✅/⚠️/❌ |

| Criterion | Status | Notes |
|-----------|--------|-------|
| All images have alt text | ✅/⚠️/❌ | [X]/[Y] have alt |
| Alt text includes keywords | ✅/⚠️/❌ | [notes] |
| Descriptive file names | ✅/⚠️/❌ | [notes] |
| Appropriate file sizes | ✅/⚠️/❌ | [notes] |
| Modern formats (WebP) | ✅/⚠️/❌ | [notes] |
| Lazy loading enabled | ✅/⚠️/❌ | [notes] |

**Image Score**: [X]/10

**Recommendations**:
1. Add alt text to image [X]: "[suggested alt text]"
2. Compress image [Y]: Currently [X]KB, should be under [Y]KB
3. Rename [filename] to [better-filename]
```

---

## Step 9: Audit Technical On-Page Elements

```markdown
## Technical On-Page Analysis

| Element | Current Value | Status | Recommendation |
|---------|---------------|--------|----------------|
| URL | [URL] | ✅/⚠️/❌ | [notes] |
| URL length | [X] chars | ✅/⚠️/❌ | [notes] |
| URL keywords | [present/absent] | ✅/⚠️/❌ | [notes] |
| Canonical tag | [URL or "missing"] | ✅/⚠️/❌ | [notes] |
| Mobile-friendly | [yes/no] | ✅/⚠️/❌ | [notes] |
| Page speed | [X]s | ✅/⚠️/❌ | [notes] |
| HTTPS | [yes/no] | ✅/⚠️/❌ | [notes] |
| Schema markup | [types or "none"] | ✅/⚠️/❌ | [notes] |

**Technical Score**: [X]/10
```

---

## Step 10: CORE-EEAT Content Quality Quick Scan

Run a quick scan of on-page-relevant CORE-EEAT items. Reference: [CORE-EEAT Benchmark](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/core-eeat-benchmark.md)

```markdown
## CORE-EEAT Quick Scan

Content-relevant items from the 80-item benchmark:

| ID | Check Item | Status | Notes |
|----|-----------|--------|-------|
| C01 | Intent Alignment | ✅/⚠️/❌ | Title promise = content delivery |
| C02 | Direct Answer | ✅/⚠️/❌ | Core answer in first 150 words |
| C09 | FAQ Coverage | ✅/⚠️/❌ | Structured FAQ present |
| C10 | Semantic Closure | ✅/⚠️/❌ | Conclusion answers opening |
| O01 | Heading Hierarchy | ✅/⚠️/❌ | H1→H2→H3, no skipping |
| O02 | Summary Box | ✅/⚠️/❌ | TL;DR or Key Takeaways |
| O03 | Data Tables | ✅/⚠️/❌ | Comparisons in tables |
| O05 | Schema Markup | ✅/⚠️/❌ | Appropriate JSON-LD |
| O06 | Section Chunking | ✅/⚠️/❌ | Single topic per section |
| R01 | Data Precision | ✅/⚠️/❌ | ≥5 precise numbers |
| R02 | Citation Density | ✅/⚠️/❌ | ≥1 per 500 words |
| R06 | Timestamp | ✅/⚠️/❌ | Updated <1 year |
| R08 | Internal Link Graph | ✅/⚠️/❌ | Descriptive anchors |
| R10 | Content Consistency | ✅/⚠️/❌ | No contradictions |
| Exp01 | First-Person Narrative | ✅/⚠️/❌ | "I tested" or "We found" |
| Ept01 | Author Identity | ✅/⚠️/❌ | Byline + bio present |
| T04 | Disclosure Statements | ✅/⚠️/❌ | Affiliate links disclosed |

**CORE-EEAT Quick Score**: [X]/17 items passing

> For a complete 80-item audit with weighted scoring, use `content-quality-auditor`.
```

---

## Step 11: Generate Audit Summary

```markdown
# On-Page SEO Audit Report

**Page**: [URL]
**Target Keyword**: [keyword]
**Audit Date**: [date]

## Overall Score: [X]/100

```
Score Breakdown:
████████░░ Title Tag: 8/10
██████░░░░ Meta Description: 6/10
█████████░ Headers: 9/10
███████░░░ Content: 7/10
██████░░░░ Keywords: 6/10
█████░░░░░ Internal Links: 5/10
████░░░░░░ Images: 4/10
████████░░ Technical: 8/10
```

## Priority Issues

### 🔴 Critical (Fix Immediately)
1. [Critical issue 1]
2. [Critical issue 2]

### 🟡 Important (Fix Soon)
1. [Important issue 1]
2. [Important issue 2]

### 🟢 Minor (Nice to Have)
1. [Minor issue 1]
2. [Minor issue 2]

## Quick Wins

These changes will have immediate impact:

1. **[Change 1]**: [Why and how]
2. **[Change 2]**: [Why and how]
3. **[Change 3]**: [Why and how]

## Detailed Recommendations

### Title Tag
- **Current**: [current title]
- **Recommended**: [new title]
- **Impact**: [expected improvement]

### Meta Description
- **Current**: [current description]
- **Recommended**: [new description]
- **Impact**: [expected improvement]

### Content Improvements
1. [Specific content change with location]
2. [Specific content change with location]

### Internal Linking
1. Add link: "[anchor]" → [destination]
2. Add link: "[anchor]" → [destination]

### Image Optimization
1. [Image 1]: [change needed]
2. [Image 2]: [change needed]

## Competitor Comparison

| Element | Your Page | Top Competitor | Gap |
|---------|-----------|----------------|-----|
| Word count | [X] | [Y] | [+/-Z] |
| Internal links | [X] | [Y] | [+/-Z] |
| Images | [X] | [Y] | [+/-Z] |
| H2 headings | [X] | [Y] | [+/-Z] |

## Action Checklist

- [ ] Update title tag
- [ ] Rewrite meta description
- [ ] Add keyword to H1
- [ ] Add [X] more internal links
- [ ] Add alt text to [X] images
- [ ] Add [X] more content sections
- [ ] Implement FAQ schema
- [ ] [Additional action items]

## Expected Results

After implementing these changes:
- Estimated ranking improvement: [X] positions
- Estimated CTR improvement: [X]%
- Estimated traffic increase: [X]%
```
