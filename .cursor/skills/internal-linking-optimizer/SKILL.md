---
name: internal-linking-optimizer
description: 'Optimize internal links: site architecture, authority distribution, orphan pages, crawl depth analysis. 内链优化/站内架构'
version: "6.0.0"
license: Apache-2.0
compatibility: "Claude Code ≥1.0, skills.sh marketplace, ClawHub marketplace, Vercel Labs skills ecosystem. No system packages required. Optional: MCP network access for SEO tool integrations."
homepage: "https://github.com/aaron-he-zhu/seo-geo-claude-skills"
when_to_use: "Use when improving internal link structure, anchor text distribution, orphan pages, or site architecture."
argument-hint: "<URL or sitemap>"
metadata:
  author: aaron-he-zhu
  version: "6.0.0"
  geo-relevance: "low"
  tags:
    - seo
    - internal-linking
    - site-architecture
    - link-equity
    - orphan-pages
    - topical-authority
    - crawl-depth
    - 内链优化
    - 内部リンク
    - 내부링크
    - enlaces-internos
  triggers:
    # EN-formal
    - "fix internal links"
    - "improve site architecture"
    - "link structure"
    - "distribute page authority"
    - "internal linking strategy"
    - "site navigation"
    - "link equity"
    # EN-casual
    - "orphan pages"
    - "site architecture is messy"
    - "pages have no links pointing to them"
    - "pages have no links"
    - "site structure is messy"
    # EN-question
    - "how to improve internal linking"
    - "how to fix orphan pages"
    # ZH-pro
    - "内链优化"
    - "站内链接"
    - "网站架构"
    - "权重传递"
    - "锚文本优化"
    # ZH-casual
    - "内链怎么做"
    - "孤立页面"
    - "网站结构乱"
    # JA
    - "内部リンク最適化"
    - "サイト構造"
    # KO
    - "내부 링크 최적화"
    - "사이트 구조"
    # ES
    - "enlaces internos"
    - "arquitectura del sitio"
    # PT
    - "links internos"
    # Misspellings
    - "internal linkng"
---

# Internal Linking Optimizer


> **[SEO & GEO Skills Library](https://github.com/aaron-he-zhu/seo-geo-claude-skills)** · 20 skills for SEO + GEO · [ClawHub](https://clawhub.ai/u/aaron-he-zhu) · [skills.sh](https://skills.sh/aaron-he-zhu/seo-geo-claude-skills)
> **System Mode**: This optimization skill follows the shared [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md) and [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md).


This skill analyzes your site's internal link structure and provides recommendations to improve SEO through strategic internal linking. It helps distribute authority, establish topical relevance, and improve crawlability.

**System role**: Optimization layer skill. It turns weak pages, structures, and technical issues into prioritized repair work.

## When This Must Trigger

Use this when the conversation involves any of these situations — even if the user does not use SEO terminology:

Use this whenever the task needs a diagnosis or repair plan that should feed directly into remediation work, not just a one-time opinion.

- Improving site architecture for SEO
- Distributing authority to important pages
- Fixing orphan pages with no internal links
- Creating topic cluster internal link strategies
- Optimizing anchor text for SEO
- Recovering pages that have lost rankings
- Planning internal links for new content

## What This Skill Does

1. **Link Structure Analysis**: Maps current internal linking patterns
2. **Authority Flow Mapping**: Shows how PageRank flows through site
3. **Orphan Page Detection**: Finds pages with no internal links
4. **Anchor Text Optimization**: Improves anchor text diversity
5. **Topic Cluster Linking**: Creates pillar-cluster link strategies
6. **Link Opportunity Finding**: Identifies where to add links
7. **Navigation Optimization**: Improves site-wide link elements

## Quick Start

Start with one of these prompts. Finish with a short handoff summary using the repository format in [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md).

### Analyze Current Structure

```
Analyze internal linking structure for [domain/sitemap]
```

```
Find internal linking opportunities for [URL]
```

### Create Linking Strategy

```
Create internal linking plan for topic cluster about [topic]
```

```
Suggest internal links for this new article: [content/URL]
```

### Fix Issues

```
Find orphan pages on [domain]
```

```
Optimize anchor text across the site
```

## Skill Contract

**Expected output**: a scored diagnosis, prioritized repair plan, and a short handoff summary ready for `memory/audits/`.

- **Reads**: the current page or site state, symptoms, prior audits, and current priorities from [CLAUDE.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/CLAUDE.md) and the shared [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md) when available.
- **Writes**: a user-facing audit or optimization plan plus a reusable summary that can be stored under `memory/audits/`.
- **Promotes**: blocking defects, repeated weaknesses, and fix priorities to `memory/open-loops.md` and `memory/decisions.md`.
- **Next handoff**: use the `Next Best Skill` below when the repair path is clear.

## Data Sources

> **Note:** All integrations are optional. This skill works without any API keys — users provide data manually when no tools are connected.

> See [CONNECTORS.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/CONNECTORS.md) for tool category placeholders.

**With ~~web crawler + ~~analytics connected:**
Claude can automatically perform a full site crawl via ~~web crawler to map the complete link graph, fetch page performance metrics from ~~analytics to identify high-value pages, and analyze link flow throughout the site. This enables data-driven internal linking strategies.

**With manual data only:**
Ask the user to provide:
1. Sitemap URL or list of important pages
2. Key page URLs that need more internal links
3. Content categories or topic clusters
4. Any existing link structure documentation

Proceed with the analysis using provided data. Note in the output which findings are from automated crawl vs. manual review.

## Instructions

When a user requests internal linking optimization:

1. **Analyze Current Internal Link Structure**

   ```markdown
   ## Internal Link Structure Analysis
   
   ### Overview
   
   **Domain**: [domain]
   **Total Pages Analyzed**: [X]
   **Total Internal Links**: [X]
   **Average Links per Page**: [X]
   
   ### Link Distribution
   
   | Links per Page | Page Count | Percentage |
   |----------------|------------|------------|
   | 0 (Orphan) | [X] | [X]% |
   | 1-5 | [X] | [X]% |
   | 6-10 | [X] | [X]% |
   | 11-20 | [X] | [X]% |
   | 20+ | [X] | [X]% |
   
   ### Top Linked Pages
   
   | Page | Internal Links | Authority | Notes |
   |------|----------------|-----------|-------|
   | [URL 1] | [X] | High | [notes] |
   | [URL 2] | [X] | High | [notes] |
   | [URL 3] | [X] | Medium | [notes] |
   
   ### Under-Linked Important Pages
   
   | Page | Current Links | Traffic | Recommended Links |
   |------|---------------|---------|-------------------|
   | [URL 1] | [X] | [X]/mo | [X]+ |
   | [URL 2] | [X] | [X]/mo | [X]+ |
   
   **Structure Score**: [X]/10
   ```

2. **Identify Orphan Pages**

   ```markdown
   ## Orphan Page Analysis
   
   ### Definition
   Orphan pages have no internal links pointing to them, making them 
   hard for users and search engines to discover.
   
   ### Orphan Pages Found: [X]
   
   | Page | Traffic | Priority | Recommended Action |
   |------|---------|----------|-------------------|
   | [URL 1] | [X]/mo | High | Link from [pages] |
   | [URL 2] | [X]/mo | Medium | Add to navigation |
   | [URL 3] | 0 | Low | Consider deleting/redirecting |
   
   ### Fix Strategy
   
   **High Priority Orphans** (have traffic/rankings):
   1. [URL] - Add links from: [relevant pages]
   2. [URL] - Add links from: [relevant pages]
   
   **Medium Priority Orphans** (potentially valuable):
   1. [URL] - Add to category/tag page
   2. [URL] - Link from related content
   
   **Low Priority Orphans** (consider removing):
   1. [URL] - Redirect to [better page]
   2. [URL] - Delete or noindex
   ```

3. **Analyze Anchor Text Distribution**

   > **CORE-EEAT alignment**: Internal linking quality maps to R08 (Internal Link Graph) in the CORE-EEAT benchmark -- use descriptive anchors, ensure links support topical authority. See [content-quality-auditor](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/content-quality-auditor/SKILL.md) for full audit.

   ```markdown
   ## Anchor Text Analysis
   
   ### Current Anchor Text Patterns
   
   **Most Used Anchors**:
   
   | Anchor Text | Count | Target Pages | Assessment |
   |-------------|-------|--------------|------------|
   | "click here" | [X] | [X] pages | ❌ Not descriptive |
   | "read more" | [X] | [X] pages | ❌ Not descriptive |
   | "[exact keyword]" | [X] | [page] | ⚠️ May be over-optimized |
   | "[descriptive phrase]" | [X] | [page] | ✅ Good |
   
   ### Anchor Text Distribution by Page
   
   **Page: [Important URL]**
   
   | Anchor Text | Source Page | Status |
   |-------------|-------------|--------|
   | "[anchor 1]" | [source URL] | ✅/⚠️/❌ |
   | "[anchor 2]" | [source URL] | ✅/⚠️/❌ |
   
   **Issues Found**:
   - Over-optimized anchors: [X] instances
   - Generic anchors: [X] instances
   - Same anchor to multiple pages: [X] instances
   
   ### Anchor Text Recommendations
   
   **For Page: [URL]**
   
   Current: "[current anchor]" used [X] times
   
   Recommended variety:
   - "[variation 1]" - Use from [page type]
   - "[variation 2]" - Use from [page type]
   - "[variation 3]" - Use from [page type]
   
   **Anchor Score**: [X]/10
   ```

4. **Create Topic Cluster Link Strategy** — Map current pillar/cluster links, recommend link structure, list specific links to add

   > **Reference**: See [references/linking-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/internal-linking-optimizer/references/linking-templates.md) for the topic cluster link strategy template (Step 4).

5. **Find Contextual Link Opportunities** — Analyze each page for topic-relevant link opportunities, prioritize high-impact additions

   > **Reference**: See [references/linking-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/internal-linking-optimizer/references/linking-templates.md) for the contextual link opportunities template (Step 5).

6. **Optimize Navigation and Footer Links** — Analyze main/footer/sidebar/breadcrumb navigation, recommend pages to add or remove

   > **Reference**: See [references/linking-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/internal-linking-optimizer/references/linking-templates.md) for the navigation optimization template (Step 6).

7. **Generate Link Implementation Plan** — Executive summary, current state metrics, phased priority actions (weeks 1-4+), implementation guide, tracking plan

   > **Reference**: See [references/linking-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/internal-linking-optimizer/references/linking-templates.md) for the full implementation plan template (Step 7).

## Validation Checkpoints

### Input Validation
- [ ] Site structure or sitemap provided (URL or file)
- [ ] Target pages or topic clusters clearly defined
- [ ] If optimizing specific page, page URL or content provided

### Output Validation
- [ ] Every recommendation cites specific data points (not generic advice)
- [ ] All link suggestions include source page, target page, and recommended anchor text
- [ ] Orphan page lists include URLs and recommended actions
- [ ] Source of each data point clearly stated (~~web crawler data, ~~analytics, user-provided, or manual analysis)

## Example

> **Reference**: See [references/linking-example.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/internal-linking-optimizer/references/linking-example.md) for a full worked example (email marketing best practices internal linking opportunities).

## Tips for Success

1. **Quality over quantity** - Add relevant links, not random ones
2. **User-first thinking** - Links should help users navigate
3. **Vary anchor text** - Avoid over-optimization
4. **Link to important pages** - Distribute authority strategically
5. **Regular audits** - Internal links need maintenance as content grows


### Save Results

After delivering audit or optimization findings to the user, ask:

> "Save these results for future sessions?"

If yes, write a dated summary to `memory/audits/internal-linking-optimizer/YYYY-MM-DD-<topic>.md` containing:
- One-line verdict or headline finding
- Top 3-5 actionable items
- Open loops or blockers
- Source data references

If any veto-level issue was found (CORE-EEAT T04, C01, R10 or CITE T03, T05, T09), also append a one-liner to `memory/hot-cache.md` without asking.

## Reference Materials

- [Link Architecture Patterns](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/internal-linking-optimizer/references/link-architecture-patterns.md) — Architecture models (hub-and-spoke, silo, flat, pyramid, mesh), anchor text diversity framework, link equity flow model, and internal link audit checklist
- [Linking Templates](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/internal-linking-optimizer/references/linking-templates.md) — Detailed output templates for steps 6-7 (navigation optimization, implementation plan)
- [Linking Example](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/internal-linking-optimizer/references/linking-example.md) — Full worked example for internal linking opportunities

## Next Best Skill

- **Primary**: [on-page-seo-auditor](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/optimize/on-page-seo-auditor/SKILL.md) — verify that revised internal links support the page-level goals.
