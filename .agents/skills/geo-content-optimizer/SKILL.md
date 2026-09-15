---
name: geo-content-optimizer
description: 'Optimize content for AI citations in ChatGPT, Perplexity, AI Overviews, Gemini, Claude. AI引用优化/GEO优化/AI搜索'
version: "6.0.0"
license: Apache-2.0
compatibility: "Claude Code ≥1.0, skills.sh marketplace, ClawHub marketplace, Vercel Labs skills ecosystem. No system packages required. Optional: MCP network access for SEO tool integrations."
homepage: "https://github.com/aaron-he-zhu/seo-geo-claude-skills"
when_to_use: "Use when optimizing content for AI engines like ChatGPT, Perplexity, AI Overviews, Gemini, Claude, or Copilot. Also for AI citation optimization and generative engine visibility."
argument-hint: "<content URL or text> [target AI engine]"
metadata:
  author: aaron-he-zhu
  version: "6.0.0"
  geo-relevance: "high"
  tags:
    - geo
    - ai-citations
    - chatgpt-optimization
    - perplexity-optimization
    - google-ai-overview
    - gemini
    - generative-engine-optimization
    - llm-citations
    - ai-seo
    - quotable-content
    - AI引用优化
    - GEO优化
    - AI最適化
    - AI최적화
    - optimizacion-ia
  triggers:
    # EN-formal
    - "optimize for AI"
    - "get cited by ChatGPT"
    - "AI optimization"
    - "appear in AI answers"
    - "GEO optimization"
    - "generative engine optimization"
    - "AI-friendly content"
    - "LLM citations"
    # EN-casual
    - "get cited by AI"
    - "show up in ChatGPT answers"
    - "AI doesn't mention my brand"
    - "make content AI-quotable"
    - "how do I get AI to mention me"
    - "ChatGPT doesn't know my brand"
    # EN-question
    - "how to appear in AI answers"
    - "how to get cited by AI"
    - "why doesn't AI mention my brand"
    # EN-competitor
    - "Perplexity optimization"
    - "how to rank in ChatGPT answers"
    - "AI Overview optimization tool"
    # ZH-pro
    - "AI引用优化"
    - "GEO优化"
    - "生成式引擎优化"
    - "AI搜索优化"
    - "AI可引用内容"
    # ZH-casual
    - "让AI引用我"
    - "ChatGPT搜不到我"
    - "AI不提我的品牌"
    - "怎么让AI推荐我"
    - "AI搜不到"
    # JA
    - "AIコンテンツ最適化"
    - "AI引用されるコンテンツ"
    - "ChatGPT対策"
    - "AI検索最適化"
    # KO
    - "AI 최적화"
    - "AI 검색 최적화"
    - "ChatGPT 인용"
    # ES
    - "optimización para IA"
    - "aparecer en respuestas de IA"
    - "citación de IA"
    # PT
    - "otimização para IA"
    - "aparecer nas respostas da IA"
    # Misspellings
    - "generative engine optimisation"
    - "GEO optimisation"
---

# GEO Content Optimizer

> **[SEO & GEO Skills Library](https://github.com/aaron-he-zhu/seo-geo-claude-skills)** · 20 skills for SEO + GEO · [ClawHub](https://clawhub.ai/u/aaron-he-zhu) · [skills.sh](https://skills.sh/aaron-he-zhu/seo-geo-claude-skills)
> **System Mode**: This build skill follows the shared [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md) and [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md).


This skill optimizes content to appear in AI-generated responses. As AI systems increasingly answer user queries directly, getting cited by these systems directly impacts visibility.

**System role**: Build layer skill. It turns briefs and signals into assets that other skills can review, publish, and monitor.

## When This Must Trigger

Use this when the conversation involves any of these situations — even if the user does not use SEO terminology:

Use this whenever the task needs a shippable asset or transformation that should feed directly into quality review, deployment, or monitoring.

- Optimizing existing content for AI citations
- Creating new content designed for both SEO and GEO
- Improving chances of appearing in AI Overviews
- Making content more quotable by AI systems
- Adding authority signals that AI systems trust
- Structuring content for AI comprehension
- Competing for visibility in the AI-first search era

## What This Skill Does

1. **Citation Optimization**: Makes content more likely to be quoted by AI
2. **Structure Enhancement**: Formats content for AI comprehension
3. **Authority Building**: Adds signals that AI systems trust
4. **Factual Enhancement**: Improves accuracy and verifiability
5. **Quote Creation**: Creates memorable, citeable statements
6. **Source Attribution**: Adds proper citations that AI can verify
7. **GEO Scoring**: Evaluates content's AI-friendliness

## Quick Start

Start with one of these prompts. Finish with a short handoff summary using the repository format in [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md).

### Optimize Existing Content

```
Optimize this content for GEO/AI citations: [content or URL]
```

```
Make this article more likely to be cited by AI systems
```

### Create GEO-Optimized Content

```
Write content about [topic] optimized for both SEO and GEO
```

### GEO Audit

```
Audit this content for GEO readiness and suggest improvements
```

## Skill Contract

**Expected output**: a ready-to-use asset or implementation-ready transformation plus a short handoff summary ready for `memory/content/`.

- **Reads**: the brief, target keywords, entity inputs, quality constraints, and prior decisions from [CLAUDE.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/CLAUDE.md) and the shared [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md) when available.
- **Writes**: a user-facing content, metadata, or schema deliverable plus a reusable summary that can be stored under `memory/content/`.
- **Promotes**: approved angles, messaging choices, missing evidence, and publish blockers to `CLAUDE.md`, `memory/decisions.md`, and `memory/open-loops.md`.
- **Next handoff**: use the `Next Best Skill` below when the asset is ready for review or deployment.

## Data Sources

> See [CONNECTORS.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/CONNECTORS.md) for tool category placeholders.

> **Note:** All integrations are optional. This skill works without any API keys — users provide data manually when no tools are connected.

**With ~~AI monitor + ~~SEO tool connected:**
Automatically pull AI citation patterns (which content is being cited by ChatGPT, Claude, Perplexity), current AI visibility scores, competitor citation frequency, and AI Overview appearance tracking.

**With manual data only:**
Ask the user to provide:
1. Target queries where they want AI citations
2. Current content URL or full content text
3. Any known instances where competitors are being cited by AI

Proceed with the full workflow using provided data. Note in the output which metrics are from automated collection vs. user-provided data.

## Instructions

When a user requests GEO optimization:

1. **Load CORE-EEAT GEO-First Optimization Targets**

   Before optimizing, load GEO-critical items from the [CORE-EEAT Benchmark](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/core-eeat-benchmark.md):

   ```markdown
   ### CORE-EEAT GEO-First Targets

   These items have the highest impact on AI engine citation. Use as optimization checklist:

   **Top 6 Priority Items**:
   | Rank | ID | Standard | Why It Matters |
   |------|----|----------|---------------|
   | 1 | C02 | Direct Answer in first 150 words | All engines extract from first paragraph |
   | 2 | C09 | Structured FAQ with Schema | Directly matches AI follow-up queries |
   | 3 | O03 | Data in tables, not prose | Most extractable structured format |
   | 4 | O05 | JSON-LD Schema Markup | Helps AI understand content type |
   | 5 | E01 | Original first-party data | AI prefers exclusive, verifiable sources |
   | 6 | O02 | Key Takeaways / Summary Box | First choice for AI summary citations |

   **All GEO-First Items** (optimize for all when possible):
   C02, C04, C05, C07, C08, C09 | O02, O03, O04, O05, O06, O09
   R01, R02, R03, R04, R05, R07, R09 | E01, E02, E03, E04, E06, E08, E09, E10
   Exp10 | Ept05, Ept08 | A08

   **AI Engine Preferences**:
   | Engine | Priority Items |
   |--------|----------------|
   | Google AI Overview | C02, O03, O05, C09 |
   | ChatGPT Browse | C02, R01, R02, E01 |
   | Perplexity AI | E01, R03, R05, Ept05 |
   | Claude | R04, Ept08, Exp10, R03 |

   _Full benchmark: [references/core-eeat-benchmark.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/core-eeat-benchmark.md)_
   ```

2. **Analyze Current Content**

   ```markdown
   ## GEO Analysis: [Content Title]
   
   ### Current State Assessment
   
   | GEO Factor | Current Score (1-10) | Notes |
   |------------|---------------------|-------|
   | Clear definitions | [X] | [notes] |
   | Quotable statements | [X] | [notes] |
   | Factual density | [X] | [notes] |
   | Source citations | [X] | [notes] |
   | Q&A format | [X] | [notes] |
   | Authority signals | [X] | [notes] |
   | Content freshness | [X] | [notes] |
   | Structure clarity | [X] | [notes] |
   | **GEO Readiness** | **[avg]/10** | **Average across factors** |
   
   **Primary Weaknesses**:
   1. [Weakness 1]
   2. [Weakness 2]
   3. [Weakness 3]
   
   **Quick Wins**:
   1. [Quick improvement 1]
   2. [Quick improvement 2]
   ```

3. **Apply GEO Optimization Techniques**

   > **GEO fundamentals**: AI systems prioritize content that is authoritative (expert credentials, proper citations), accurate (verifiable, up-to-date), clear (well-structured, unambiguous), and quotable (standalone answers, specific data). See [references/geo-optimization-techniques.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/build/geo-content-optimizer/references/geo-optimization-techniques.md) for details.

   Apply the six core optimization techniques: definition optimization, quotable statement creation, authority signal enhancement, structure optimization, factual density improvement, and FAQ schema implementation.

   > **Reference**: See [references/geo-optimization-techniques.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/build/geo-content-optimizer/references/geo-optimization-techniques.md) for detailed before/after examples, templates, and checklists for each technique.

   Key principles:
   - **Definitions**: 25-50 words, standalone, starting with the term
   - **Quotable statements**: Specific statistics with sources, verifiable facts
   - **Authority signals**: Expert quotes with credentials, proper source citations
   - **Structure**: Q&A format, comparison tables, numbered lists
   - **Factual density**: Replace vague claims with specific data points
   - **FAQ schema**: JSON-LD FAQPage markup matching visible content

4. **Generate GEO-Optimized Output**

   ```markdown
   ## GEO Optimization Report

   ### Changes Made

   **Definitions Added/Improved**:
   1. [Definition 1] - [location in content]
   2. [Definition 2] - [location in content]

   **Quotable Statements Created**:
   1. "[Statement 1]"
   2. "[Statement 2]"

   **Authority Signals Added**:
   1. [Expert quote/citation]
   2. [Source attribution]

   **Structural Improvements**:
   1. [Change 1]
   2. [Change 2]

   ### Before/After GEO Score

   | GEO Factor | Before (1-10) | After (1-10) | Change |
   |------------|---------------|--------------|--------|
   | Clear definitions | [X] | [X] | +[X] |
   | Quotable statements | [X] | [X] | +[X] |
   | Factual density | [X] | [X] | +[X] |
   | Source citations | [X] | [X] | +[X] |
   | Q&A format | [X] | [X] | +[X] |
   | Authority signals | [X] | [X] | +[X] |
   | **Overall GEO Score** | **[avg]/10** | **[avg]/10** | **+[X]** |

   ### AI Query Coverage

   This content is now optimized to answer:
   - "What is [topic]?" ✅
   - "How does [topic] work?" ✅
   - "Why is [topic] important?" ✅
   - "[Topic] vs [alternative]" ✅
   - "Best [topic] for [use case]" ✅
   ```

5. **CORE-EEAT GEO Self-Check**

    After optimization, verify GEO-First items:

    ```markdown
    ### CORE-EEAT GEO Post-Optimization Check

    | ID | Standard | Status | Notes |
    |----|----------|--------|-------|
    | C02 | Direct Answer in first 150 words | ✅/⚠️/❌ | [notes] |
    | C04 | Key terms defined on first use | ✅/⚠️/❌ | [notes] |
    | C09 | Structured FAQ with Schema | ✅/⚠️/❌ | [notes] |
    | O02 | Summary Box / Key Takeaways | ✅/⚠️/❌ | [notes] |
    | O03 | Comparisons in tables | ✅/⚠️/❌ | [notes] |
    | O05 | JSON-LD Schema Markup | ✅/⚠️/❌ | [notes] |
    | O06 | Section chunking (3–5 sentences) | ✅/⚠️/❌ | [notes] |
    | R01 | ≥5 precise data points with units | ✅/⚠️/❌ | [notes] |
    | R02 | ≥1 citation per 500 words | ✅/⚠️/❌ | [notes] |
    | R04 | Claims backed by evidence | ✅/⚠️/❌ | [notes] |
    | R07 | Full entity names | ✅/⚠️/❌ | [notes] |
    | E01 | Original first-party data | ✅/⚠️/❌ | [notes] |
    | Exp10 | Limitations acknowledged | ✅/⚠️/❌ | [notes] |
    | Ept08 | Reasoning transparency | ✅/⚠️/❌ | [notes] |

    **Items Needing Attention**: [list any ⚠️/❌ items]

    _For full 80-item audit, use [content-quality-auditor](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/content-quality-auditor/SKILL.md)_
    ```

## Validation Checkpoints

### Input Validation
- [ ] Content source identified (URL, full text, or content draft)
- [ ] Target AI queries or topics clearly defined
- [ ] Current GEO baseline assessed (if optimizing existing content)

### Output Validation
- [ ] At least 3 clear, quotable definitions added
- [ ] Factual density improved with at least 5 verifiable statistics
- [ ] All claims have source citations from authoritative sources
- [ ] Q&A format sections cover top 5 user queries
- [ ] GEO score improvement of at least 50% from baseline
- [ ] Source of each data point clearly stated (~~AI monitor data, user-provided, or estimated)

## Example

**User**: "Optimize this paragraph for GEO: 'Email marketing is a good way to reach customers. It's been around for a while and many businesses use it. You can send newsletters, promotions, and other messages.'"

**Output**:

```markdown
## GEO-Optimized Version

**Email marketing** is a digital marketing strategy that uses email to promote 
products, build customer relationships, and drive conversions. According to 
the Data & Marketing Association, email marketing delivers an average ROI 
of $42 for every $1 invested, making it the highest-performing digital 
marketing channel.

### Key email marketing formats include:

1. **Newsletters**: Regular updates sharing company news, industry insights, 
   and valuable content to maintain subscriber engagement
2. **Promotional emails**: Time-sensitive offers, discounts, and product 
   announcements designed to drive immediate sales
3. **Transactional emails**: Order confirmations, shipping updates, and 
   account notifications with 8x higher open rates than marketing emails
4. **Automated sequences**: Pre-scheduled email series triggered by user 
   actions, such as welcome series or abandoned cart reminders

> **Key statistic**: 81% of small businesses rely on email as their primary 
> customer acquisition channel (Emarsys, 2024).

---

### Changes Made:

Changes: added clear definition, 2 stats with sources, structured list, DMA/Emarsys citations, 3 quotable facts. **GEO Score**: 1/10 → 8/10.
```

## GEO Optimization Checklist

> **Reference**: See the GEO Readiness Checklist in [references/geo-optimization-techniques.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/build/geo-content-optimizer/references/geo-optimization-techniques.md) for the full checklist covering definitions, quotable content, authority, structure, and technical elements.

## Tips for Success

1. **Answer the question first** - Put the answer in the first sentence
2. **Be specific** - Vague content doesn't get cited
3. **Cite sources** - AI systems trust verifiable information
4. **Stay current** - Update statistics and facts regularly
5. **Match query format** - Questions deserve direct answers
6. **Build authority** - Expert credentials increase citation likelihood


### Save Results

After delivering content or optimization output to the user, ask:

> "Save these results for future sessions?"

If yes, write a dated summary to `memory/content/YYYY-MM-DD-<topic>.md` containing:
- One-line description of what was created
- Target keyword and content type
- Open loops or items needing review
- Source data references

**Gate check recommended**: Run content-quality-auditor before publishing (PostToolUse hook will remind automatically).

If any findings should influence ongoing strategy, recommend promoting key conclusions to `memory/hot-cache.md`.

## Reference Materials

- [AI Citation Patterns](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/build/geo-content-optimizer/references/ai-citation-patterns.md) - How Google AI Overviews, ChatGPT, Perplexity, and Claude select and cite sources
- [Quotable Content Examples](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/build/geo-content-optimizer/references/quotable-content-examples.md) - Before/after examples of content optimized for AI citation

## Next Best Skill

- **Primary**: [content-quality-auditor](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/content-quality-auditor/SKILL.md) — verify the optimized content is strong enough to ship and cite.
