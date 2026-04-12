---
name: on-page-seo-auditor
description: 'Audit on-page SEO: titles, headers, images, links with scored report and fix priorities. 页面SEO审计/排名诊断'
version: "6.0.0"
license: Apache-2.0
compatibility: "Claude Code ≥1.0, skills.sh marketplace, ClawHub marketplace, Vercel Labs skills ecosystem. No system packages required. Optional: MCP network access for SEO tool integrations."
homepage: "https://github.com/aaron-he-zhu/seo-geo-claude-skills"
when_to_use: "Use when auditing a page's on-page SEO health, checking heading structure, keyword placement, image optimization, or content quality signals."
argument-hint: "<URL> [keyword]"
allowed-tools: WebFetch
metadata:
  author: aaron-he-zhu
  version: "6.0.0"
  geo-relevance: "medium"
  tags:
    - seo
    - on-page-audit
    - page-optimization
    - seo-score
    - content-audit
    - h1-optimization
    - meta-audit
    - seo-checklist
    - yoast-alternative
    - screaming-frog-alternative
    - 页面SEO
    - 网页优化
    - ページSEO
    - 페이지감사
    - auditoria-seo
  triggers:
    # EN-formal
    - "audit page SEO"
    - "on-page SEO check"
    - "SEO score"
    - "page optimization"
    - "on-page audit"
    - "SEO page analysis"
    - "content audit"
    # EN-casual
    - "what SEO issues does this page have"
    - "check my page"
    - "score my page"
    - "why isn't this page ranking"
    - "what's wrong with this page's SEO"
    - "is my page optimized"
    - "my rankings tanked"
    - "why did my rankings drop"
    # EN-question
    - "why is my page not ranking"
    - "how do I improve my page SEO"
    - "what SEO problems does this page have"
    # EN-competitor
    - "Screaming Frog alternative"
    - "Yoast SEO alternative"
    # ZH-pro
    - "页面SEO审计"
    - "网页优化检查"
    - "SEO评分"
    - "页面诊断"
    - "页面优化分析"
    # ZH-casual
    - "页面有什么问题"
    - "为什么排不上去"
    - "检查一下我的页面"
    - "SEO打分"
    - "排名上不去怎么办"
    - "网页收录问题"
    # JA
    - "ページSEO監査"
    - "オンページSEO"
    - "ページ最適化"
    - "SEOスコア"
    # KO
    - "페이지 SEO 감사"
    - "온페이지 SEO"
    - "SEO 점수"
    - "이 페이지 뭐가 문제야?"
    - "왜 순위가 안 올라가?"
    - "SEO 점수 확인해줘"
    # ES
    - "auditoría SEO on-page"
    - "análisis de página SEO"
    - "puntuación SEO"
    # PT
    - "auditoria SEO on-page"
    # Misspellings
    - "on page SEO aduit"
    - "SEO scroe"
---

# On-Page SEO Auditor


> **[SEO & GEO Skills Library](https://github.com/aaron-he-zhu/seo-geo-claude-skills)** · 20 skills for SEO + GEO · [ClawHub](https://clawhub.ai/u/aaron-he-zhu) · [skills.sh](https://skills.sh/aaron-he-zhu/seo-geo-claude-skills)
> **System Mode**: This optimization skill follows the shared [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md) and [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md).


This skill performs detailed on-page SEO audits to identify issues and optimization opportunities. It analyzes all on-page elements that affect search rankings and provides actionable recommendations.

**System role**: Optimization layer skill. It turns weak pages, structures, and technical issues into prioritized repair work.

## When This Must Trigger

Use this when the conversation involves any of these situations — even if the user does not use SEO terminology:

Use this whenever the task needs a diagnosis or repair plan that should feed directly into remediation work, not just a one-time opinion.

- Auditing pages before or after publishing
- Identifying why a page isn't ranking well
- Optimizing existing content for better performance
- Creating pre-publish SEO checklists
- Comparing your on-page SEO to competitors
- Systematic site-wide SEO improvements
- Training team members on SEO best practices

## What This Skill Does

1. **Title Tag Analysis**: Evaluates title optimization and CTR potential
2. **Meta Description Review**: Checks description quality and length
3. **Header Structure Audit**: Analyzes H1-H6 hierarchy
4. **Content Quality Assessment**: Reviews content depth and optimization
5. **Keyword Usage Analysis**: Checks keyword placement and density
6. **Internal Link Review**: Evaluates internal linking structure
7. **Image Optimization Check**: Audits alt text and file optimization
8. **Technical On-Page Review**: Checks URL, canonical, and mobile factors

## Quick Start

Start with one of these prompts. Finish with a short handoff summary using the repository format in [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md).

### Audit a Single Page

```
Audit the on-page SEO of [URL]
```

```
Check SEO issues on this page targeting [keyword]: [URL/content]
```

### Compare Against Competitors

```
Compare on-page SEO of [your URL] vs [competitor URL] for [keyword]
```

### Audit Content Before Publishing

```
Pre-publish SEO audit for this content targeting [keyword]: [content]
```

## Skill Contract

**Expected output**: a scored diagnosis, prioritized repair plan, and a short handoff summary ready for `memory/audits/`.

- **Reads**: the current page or site state, symptoms, prior audits, and current priorities from [CLAUDE.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/CLAUDE.md) and the shared [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md) when available.
- **Writes**: a user-facing audit or optimization plan plus a reusable summary that can be stored under `memory/audits/`.
- **Promotes**: blocking defects, repeated weaknesses, and fix priorities to `memory/open-loops.md` and `memory/decisions.md`.
- **Next handoff**: use the `Next Best Skill` below when the repair path is clear.

## Data Sources

> See [CONNECTORS.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/CONNECTORS.md) for tool category placeholders.

**With ~~SEO tool + ~~web crawler connected:**
Claude can automatically pull page HTML via ~~web crawler, fetch keyword search volume and difficulty from ~~SEO tool, retrieve click-through rate data from ~~search console, and download competitor pages for comparison. This enables fully automated audits with live data.

**With manual data only:**
Ask the user to provide:
1. Page URL or complete HTML content
2. Target primary and secondary keywords
3. Competitor page URLs for comparison (optional)

Proceed with the full audit using provided data. Note in the output which findings are from automated crawl vs. manual review.

## Instructions

When a user requests an on-page SEO audit:

1. **Gather Page Information**

   ```markdown
   ### Audit Setup
   
   **Page URL**: [URL]
   **Target Keyword**: [primary keyword]
   **Secondary Keywords**: [additional keywords]
   **Page Type**: [blog/product/landing/service]
   **Business Goal**: [traffic/conversions/authority]
   ```

2. **Audit Title Tag**

   ```markdown
   ## Title Tag Analysis
   
   **Current Title**: [title]
   **Character Count**: [X] characters
   
   | Criterion | Status | Notes |
   |-----------|--------|-------|
   | Length (50-60 chars) | ✅/⚠️/❌ | [notes] |
   | Keyword included | ✅/⚠️/❌ | Position: [front/middle/end] |
   | Keyword at front | ✅/⚠️/❌ | [notes] |
   | Unique across site | ✅/⚠️/❌ | [notes] |
   | Compelling/clickable | ✅/⚠️/❌ | [notes] |
   | Matches intent | ✅/⚠️/❌ | [notes] |
   
   **Title Score**: [X]/10
   
   **Issues Found**:
   - [Issue 1]
   - [Issue 2]
   
   **Recommended Title**:
   "[Optimized title suggestion]"
   
   **Why**: [Explanation of improvements]
   ```

3. **Audit Meta Description**

   ```markdown
   ## Meta Description Analysis
   
   **Current Description**: [description]
   **Character Count**: [X] characters
   
   | Criterion | Status | Notes |
   |-----------|--------|-------|
   | Length (150-160 chars) | ✅/⚠️/❌ | [notes] |
   | Keyword included | ✅/⚠️/❌ | [notes] |
   | Call-to-action present | ✅/⚠️/❌ | [notes] |
   | Unique across site | ✅/⚠️/❌ | [notes] |
   | Accurately describes page | ✅/⚠️/❌ | [notes] |
   | Compelling copy | ✅/⚠️/❌ | [notes] |
   
   **Description Score**: [X]/10
   
   **Issues Found**:
   - [Issue 1]
   
   **Recommended Description**:
   "[Optimized description suggestion]" ([X] chars)
   ```

4. **Audit Header Structure**

   ```markdown
   ## Header Structure Analysis
   
   ### Current Header Hierarchy
   
   ```
   H1: [H1 text]
     H2: [H2 text]
       H3: [H3 text]
       H3: [H3 text]
     H2: [H2 text]
       H3: [H3 text]
     H2: [H2 text]
   ```
   
   | Criterion | Status | Notes |
   |-----------|--------|-------|
   | Single H1 | ✅/⚠️/❌ | Found: [X] H1s |
   | H1 includes keyword | ✅/⚠️/❌ | [notes] |
   | Logical hierarchy | ✅/⚠️/❌ | [notes] |
   | H2s include keywords | ✅/⚠️/❌ | [X]/[Y] contain keywords |
   | No skipped levels | ✅/⚠️/❌ | [notes] |
   | Descriptive headers | ✅/⚠️/❌ | [notes] |
   
   **Header Score**: [X]/10
   
   **Issues Found**:
   - [Issue 1]
   - [Issue 2]
   
   **Recommended Changes**:
   - H1: [suggestion]
   - H2s: [suggestions]
   ```

5. **Audit Content Quality** — Word count, reading level, comprehensiveness, formatting, E-E-A-T signals, content elements checklist, gap identification

   > **Reference**: See [references/audit-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/on-page-seo-auditor/references/audit-templates.md) for the content quality template (Step 5).

6. **Audit Keyword Usage** — Primary/secondary keyword placement across all page elements, LSI/related terms, density analysis

   > **Reference**: See [references/audit-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/on-page-seo-auditor/references/audit-templates.md) for the keyword optimization template (Step 6).

7. **Audit Internal Links** — Link count, anchor text relevance, broken links, recommended additions

   > **Reference**: See [references/audit-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/on-page-seo-auditor/references/audit-templates.md) for the internal linking template (Step 7).

8. **Audit Images** — Alt text, file names, sizes, formats, lazy loading

   > **Reference**: See [references/audit-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/on-page-seo-auditor/references/audit-templates.md) for the image optimization template (Step 8).

9. **Audit Technical On-Page Elements** — URL, canonical, mobile, speed, HTTPS, schema

   > **Reference**: See [references/audit-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/on-page-seo-auditor/references/audit-templates.md) for the technical on-page template (Step 9).

10. **CORE-EEAT Content Quality Quick Scan** — 17 on-page-relevant items from the 80-item CORE-EEAT benchmark

    > **Reference**: See [references/audit-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/on-page-seo-auditor/references/audit-templates.md) for the CORE-EEAT quick scan template (Step 10). Full benchmark: [CORE-EEAT Benchmark](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/core-eeat-benchmark.md).

11. **Generate Audit Summary** — Overall score with visual breakdown, priority issues (critical/important/minor), quick wins, detailed recommendations, competitor comparison, action checklist, expected results

    > **Reference**: See [references/audit-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/on-page-seo-auditor/references/audit-templates.md) for the full audit summary template (Step 11).

## Validation Checkpoints

### Input Validation
- [ ] Target keyword(s) clearly specified by user
- [ ] Page content accessible (either via URL or provided HTML)
- [ ] If competitor comparison requested, competitor URL provided

### Output Validation
- [ ] Every recommendation cites specific data points (not generic advice)
- [ ] Scores based on measurable criteria, not subjective opinion
- [ ] All suggested changes include specific locations (title tag, H2 #3, paragraph 5, etc.)
- [ ] Source of each data point clearly stated (~~SEO tool data, user-provided, ~~web crawler, or manual review)

## Example

> **Reference**: See [references/audit-example.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/on-page-seo-auditor/references/audit-example.md) for a full worked example (noise-cancelling headphones audit) and page-type checklists (blog post, product page, landing page).

## Tips for Success

1. **Prioritize issues by impact** - Fix critical issues first
2. **Compare to competitors** - See what's working for top rankings
3. **Balance optimization and readability** - Don't over-optimize
4. **Audit regularly** - Content degrades over time
5. **Test changes** - Track ranking changes after updates

> **Scoring details**: For the complete weight distribution, scoring scale, issue resolution playbook, and industry benchmarks, see [references/scoring-rubric.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/on-page-seo-auditor/references/scoring-rubric.md).


### Save Results

After delivering audit or optimization findings to the user, ask:

> "Save these results for future sessions?"

If yes, write a dated summary to `memory/audits/on-page-seo-auditor/YYYY-MM-DD-<topic>.md` containing:
- One-line verdict or headline finding
- Top 3-5 actionable items
- Open loops or blockers
- Source data references

If any veto-level issue was found (CORE-EEAT T04, C01, R10 or CITE T03, T05, T09), also append a one-liner to `memory/hot-cache.md` without asking.

## Reference Materials

- [Scoring Rubric](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/on-page-seo-auditor/references/scoring-rubric.md) — Detailed scoring criteria, weight distribution, and grade boundaries for on-page audits
- [Audit Templates](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/on-page-seo-auditor/references/audit-templates.md) — Detailed output templates for steps 5-11 (content quality, keywords, links, images, technical, CORE-EEAT scan, audit summary)
- [Audit Example & Checklists](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/on-page-seo-auditor/references/audit-example.md) — Full worked example and page-type checklists (blog, product, landing page)

## Next Best Skill

- **Primary**: [content-refresher](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/content-refresher/SKILL.md) — turn page-level findings into concrete edits.
