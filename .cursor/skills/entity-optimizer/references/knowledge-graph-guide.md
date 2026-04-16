# Knowledge Graph Optimization Guide

> Part of [entity-optimizer](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/entity-optimizer/SKILL.md). See also: [entity-signal-checklist.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/entity-optimizer/references/entity-signal-checklist.md)

Comprehensive playbook for establishing and maintaining entity presence across Google Knowledge Graph, Wikidata, Wikipedia, and other knowledge bases.

## How Knowledge Graphs Work

### The Entity Web

Knowledge graphs are interconnected databases of entities and their relationships. Search engines and AI systems use them as ground truth for entity understanding.

```
Your Entity
├── is described by → Wikidata entry
├── is described by → Wikipedia article
├── is described by → Schema.org markup on your site
├── is linked to → Social profiles (LinkedIn, X, etc.)
├── is mentioned by → News articles, industry sites
├── is associated with → Topics, industries, other entities
└── is recognized by → Google Knowledge Graph, Bing Satori, AI training data
```

### Which Knowledge Graphs Matter

| Knowledge Graph | Who Uses It | Impact |
|----------------|-------------|--------|
| **Google Knowledge Graph** | Google Search, Google AI | Powers Knowledge Panels, rich results, entity understanding in search |
| **Wikidata** | Google, Bing, Apple, Amazon, AI systems | Open data feeds multiple knowledge graphs; primary structured data source |
| **Wikipedia** | Google, all AI systems | Training data for every major LLM; Knowledge Panel descriptions often sourced here |
| **Bing Satori** | Bing, Copilot | Powers Bing's entity understanding and Microsoft Copilot |
| **Schema.org (your site)** | All search engines, AI crawlers | First-party structured data you control directly |
| **DBpedia** | Research, some AI systems | Auto-extracted from Wikipedia; relevant for academic/research entities |

### Data Flow

```
Your Website (Schema.org) ─┐
Wikidata ──────────────────┤
Wikipedia ─────────────────┼──→ Google Knowledge Graph ──→ Knowledge Panel
Industry Directories ──────┤                              AI Search Results
News/Media Mentions ───────┤                              Rich Results
Social Profiles ───────────┘
```

Understanding this flow is key: you influence the Knowledge Graph by controlling the **source signals** that feed it.

## Google Knowledge Graph

### Getting Into the Knowledge Graph

There is no "submit to Knowledge Graph" form. Google builds its Knowledge Graph from multiple sources. To get included:

1. **Have a Wikidata entry** — This is the most direct path
2. **Earn a Wikipedia article** — Strongest single signal
3. **Implement Schema.org markup** — Provides structured self-description
4. **Get mentioned on authoritative sites** — Third-party validation
5. **Build branded search demand** — Signals that users look for your entity

### Checking Your Knowledge Graph Status

**Method 1: Google Search**
Search for your entity name in quotes. If a Knowledge Panel appears on the right, you're in the Knowledge Graph.

**Method 2: Knowledge Graph API**
```
GET https://kgsearch.googleapis.com/v1/entities:search?query=[entity]&key=[API_KEY]
```

Response includes:
- `@id`: Your Knowledge Graph ID (e.g., `kg:/m/0wrt4g`)
- `name`: Entity name as Google understands it
- `description`: Short entity description
- `detailedDescription`: Longer description (usually from Wikipedia)
- `resultScore`: Confidence score (higher = more established entity)

**Method 3: ~~knowledge graph**
If connected, query directly for entity status and attributes.

### Claiming Your Knowledge Panel

1. Search for your entity on Google
2. If Knowledge Panel appears, look for "Claim this knowledge panel" link at bottom
3. Verify via official website, Search Console, YouTube, or other Google property
4. Once claimed, you can suggest edits (but Google has final say)

### Common Knowledge Panel Fixes

| Problem | Solution |
|---------|----------|
| **No Knowledge Panel** | Build Wikidata entry + Schema.org + authoritative mentions. Timeline: 2-6 months. |
| **Wrong image** | Update preferred image on: Wikidata (P18), About page, social profiles. Claim panel and suggest preferred image. |
| **Wrong description** | Edit Wikidata description. Update first paragraph of About page and Wikipedia article. |
| **Missing attributes** | Add properties to Wikidata and Schema.org. Claim panel and suggest additions. |
| **Outdated information** | Update Wikidata, About page, Wikipedia, and social profiles. Request refresh via claimed panel. |
| **Wrong entity shown** | Disambiguation needed. See Wikidata section below for disambiguation strategy. |

## Wikidata

### Why Wikidata Is Critical

Wikidata is the **single most influential editable knowledge base** for entity optimization:
- Google uses it as a primary source for Knowledge Panels
- Bing uses it for Satori knowledge graph
- AI systems reference it during entity resolution
- It's open and you can edit it (within their guidelines)

### Creating a Wikidata Entry

#### Step 1: Check Eligibility

Wikidata requires "notability" — the entity must be referenced in at least one external source. Unlike Wikipedia, the notability bar is lower: a company mentioned in a news article, a product with reviews, or a person with published work typically qualifies.

#### Step 2: Create the Item

1. Go to https://www.wikidata.org/wiki/Special:NewItem
2. Fill in:
   - **Label**: Official entity name
   - **Description**: Short description (e.g., "American software company" or "SEO optimization tool")
   - **Aliases**: Alternative names, abbreviations, former names

#### Step 3: Add Core Statements

Essential properties for each entity type:

**Organizations:**
| Property | Code | Example |
|----------|------|---------|
| instance of | P31 | business (Q4830453) or specific type |
| official website | P856 | https://example.com |
| inception | P571 | 2020-01-15 |
| country | P17 | United States (Q30) |
| headquarters location | P159 | San Francisco (Q62) |
| industry | P452 | software industry (Q638608) |
| founded by | P112 | [founder's Wikidata item] |
| CEO | P169 | [CEO's Wikidata item] |

**Persons:**
| Property | Code | Example |
|----------|------|---------|
| instance of | P31 | human (Q5) |
| occupation | P106 | software engineer (Q183888) |
| employer | P108 | [company Wikidata item] |
| educated at | P69 | [university Wikidata item] |
| country of citizenship | P27 | [country item] |
| official website | P856 | https://example.com |

**Products/Software:**
| Property | Code | Example |
|----------|------|---------|
| instance of | P31 | software (Q7397) or web application (Q189210) |
| developer | P178 | [company Wikidata item] |
| official website | P856 | https://example.com |
| programming language | P277 | Python (Q28865) |
| operating system | P306 | Linux (Q388) |
| software license | P275 | Apache-2.0 (Q13785927) |
| inception | P571 | 2023-06-01 |

#### Step 4: Add External Identifiers

These link your Wikidata item to other knowledge bases:

| Identifier | Code | Purpose |
|-----------|------|---------|
| official website | P856 | Primary web presence |
| X (Twitter) username | P2002 | Social presence |
| LinkedIn organization ID | P4264 | Professional presence |
| GitHub username | P2037 | Technical presence |
| CrunchBase ID | P2087 | Business data |
| Google Knowledge Graph ID | P2671 | Google entity link |
| App Store ID | P3861 | Mobile presence |

#### Step 5: Add References

**Every statement must have a reference.** Unreferenced statements may be removed.

Good reference sources:
- Official website (for factual claims like founding date)
- News articles (for events, milestones)
- Industry reports (for market position)
- Government registries (for legal entity information)

### Wikidata Maintenance

| Task | Frequency | Why |
|------|-----------|-----|
| Review existing statements | Quarterly | Ensure accuracy; update changed information |
| Add new properties | When new information available | Keep entry comprehensive |
| Check for vandalism | Monthly | Others can edit your entry |
| Add new references | When new coverage appears | Strengthen statement credibility |
| Update identifiers | When new profiles created | Keep links current |

## Wikipedia

### Notability Requirements

Wikipedia requires entities to meet "general notability guidelines" (GNG):
- **Significant coverage** in **reliable, independent sources**
- Coverage must be **non-trivial** (not just a mention or directory listing)
- Sources must be **independent** of the entity (not press releases, not entity's own content)

### Building Toward Notability

If the entity doesn't have a Wikipedia article yet:

1. **Audit existing coverage**: Search Google News, academic databases, and industry publications for mentions
2. **Identify gaps**: What kinds of coverage are missing?
3. **Build coverage first, then article**: The article is the last step, not the first

Coverage-building strategies:
| Strategy | Timeline | Notability Impact |
|----------|----------|-------------------|
| Industry report mentions | 3-6 months | Medium — depends on report authority |
| News article coverage | 1-3 months | High — especially from recognized publications |
| Conference speaking + coverage | 3-12 months | Medium — needs post-event coverage |
| Academic paper citations | 6-12+ months | High — very strong for GNG |
| Award recognition | Variable | Medium — depends on award authority |
| Book publication or feature | 6-12+ months | High — strong independent source |

### Wikipedia Article Best Practices

**DO:**
- Write in neutral, encyclopedic tone
- Use only independent, reliable sources as references
- Follow Wikipedia's Manual of Style
- Disclose any conflict of interest on your Talk page
- Let the community review and improve the article

**DO NOT:**
- Write promotional content
- Use the entity's own website as a primary source
- Create the article from a company account without disclosure
- Remove criticism or negative but sourced information
- Pay someone to write the article without disclosure (violates Wikipedia policy)

### Wikipedia's Impact on AI

Wikipedia is disproportionately important for AI systems because:
- It's in the training data of every major LLM
- AI systems treat it as a high-trust source
- Wikipedia's structured format makes it easy for AI to extract and cite
- The first paragraph of a Wikipedia article often becomes the AI's entity definition

This makes Wikipedia presence one of the highest-impact entity optimization actions for GEO.

## Schema.org Entity Markup

### Minimum Viable Entity Schema

Every entity should have at minimum this markup on the homepage:

**Organization:**
```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "https://example.com/#organization",
  "name": "Example Corp",
  "url": "https://example.com",
  "logo": "https://example.com/logo.png",
  "description": "Example Corp is a [what it is] that [what it does].",
  "foundingDate": "2020-01-15",
  "founder": {
    "@type": "Person",
    "name": "Jane Smith",
    "@id": "https://example.com/about/jane-smith#person"
  },
  "sameAs": [
    "https://www.wikidata.org/wiki/Q12345678",
    "https://en.wikipedia.org/wiki/Example_Corp",
    "https://www.linkedin.com/company/example-corp",
    "https://x.com/examplecorp",
    "https://www.crunchbase.com/organization/example-corp"
  ]
}
```

**Person:**
```json
{
  "@context": "https://schema.org",
  "@type": "Person",
  "@id": "https://example.com/about/jane-smith#person",
  "name": "Jane Smith",
  "url": "https://example.com/about/jane-smith",
  "image": "https://example.com/photos/jane-smith.jpg",
  "jobTitle": "CEO",
  "worksFor": {
    "@type": "Organization",
    "@id": "https://example.com/#organization"
  },
  "description": "Jane Smith is [who they are] specializing in [expertise areas].",
  "sameAs": [
    "https://www.wikidata.org/wiki/Q87654321",
    "https://www.linkedin.com/in/janesmith",
    "https://x.com/janesmith"
  ]
}
```

### sameAs Best Practices

The `sameAs` property is the **primary entity disambiguation signal** in Schema.org. It tells search engines "this is the same entity as the one on these other platforms."

**Must include (when available):**
1. Wikidata URL (most important for Knowledge Graph)
2. Wikipedia URL
3. LinkedIn URL
4. Official social media profiles

**Include when relevant:**
5. CrunchBase URL
6. GitHub URL
7. IMDb URL (for people in entertainment)
8. Industry directory URLs

**Common mistakes:**
- Linking to generic pages instead of entity-specific URLs
- Inconsistent: Schema says "Example Corp" but LinkedIn says "Example Corporation"
- Missing Wikidata link (this is the single most impactful sameAs)
- Including dead or redirecting URLs

### Cross-Page Entity Consistency

Every page on the site should reference the same entity with the same `@id`:

```json
{
  "@type": "WebPage",
  "publisher": {
    "@type": "Organization",
    "@id": "https://example.com/#organization"
  }
}
```

For articles:
```json
{
  "@type": "Article",
  "author": {
    "@type": "Person",
    "@id": "https://example.com/about/jane-smith#person"
  },
  "publisher": {
    "@type": "Organization",
    "@id": "https://example.com/#organization"
  }
}
```

This creates a consistent entity graph that search engines can confidently map to Knowledge Graph entries.

## Monitoring Entity Health

### Quarterly Entity Health Check

| Check | How | What to Look For |
|-------|-----|-----------------|
| Knowledge Panel accuracy | Google entity name | Correct info, image, attributes |
| Wikidata entry | Visit Wikidata page | No vandalism, info still current |
| AI entity resolution | Query 3+ AI systems | Accurate recognition and description |
| Schema.org validation | Google Rich Results Test | No errors, complete entity data |
| Branded search SERP | Google "[entity name]" | Clean SERP, no disambiguation issues |
| Social profile consistency | Visit all profiles | Same name, description, links |

### Entity Health Metrics to Track

| Metric | Tool | Target |
|--------|------|--------|
| Knowledge Panel presence | Google Search | Present and accurate |
| Branded search CTR | ~~search console | > 50% for exact brand name |
| AI recognition rate | Manual testing | Recognized by 3/3 major AI systems |
| Wikidata completeness | Wikidata | 15+ properties with references |
| Schema.org error count | Google Search Console | 0 errors |
| Brand mention volume | ~~brand monitor | Stable or growing trend |

### Recovery Playbooks

**Entity disappeared from Knowledge Graph:**
1. Check if Wikidata entry was deleted or merged
2. Verify Schema.org markup hasn't changed
3. Look for major algorithm updates that might have affected entity recognition
4. Rebuild signals: start with Wikidata, then Schema.org, then external mentions
5. Timeline: 2-8 weeks for recovery

**AI systems giving incorrect entity info:**
1. Identify which sources have incorrect information
2. Correct information at source (Wikidata, Wikipedia, About page)
3. AI systems will update over time (training data refresh + live search)
4. For urgent issues, some AI systems have feedback mechanisms
5. Timeline: weeks to months depending on AI system update cycles

**Knowledge Panel showing wrong entity:**
1. Claim the Knowledge Panel (if you haven't already)
2. Strengthen disambiguation signals (see SKILL.md Disambiguation Strategy)
3. Add qualifier to entity name if needed
4. Build more unique entity signals (original content, specific topic associations)
5. Timeline: 1-3 months
