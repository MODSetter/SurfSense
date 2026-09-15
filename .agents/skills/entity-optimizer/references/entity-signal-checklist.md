# Entity Signal Checklist

> Part of [entity-optimizer](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/entity-optimizer/SKILL.md). See also: [knowledge-graph-guide.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/entity-optimizer/references/knowledge-graph-guide.md)

Complete checklist of entity signals organized by priority and verification method. Use this as a systematic audit guide — work through each signal, verify its status, and note actions needed.

## Priority 1: Foundation Signals (Must-Have)

These signals form the minimum viable entity identity. Without them, search engines and AI systems cannot reliably identify the entity.

### On-Site Structured Data

| # | Signal | Verification Method | Pass Criteria |
|---|--------|-------------------|---------------|
| 1 | Organization or Person schema on homepage | Run Google Rich Results Test on homepage | Schema present with name, url, logo, description |
| 2 | sameAs property links to all authoritative profiles | Inspect schema markup | Links to Wikipedia, Wikidata, LinkedIn, social profiles |
| 3 | Consistent @id used across all pages | Inspect schema on 5+ pages | Same @id (typically homepage URL + #organization) on every page |
| 4 | About page exists with entity-rich content | Manual review | First paragraph defines entity clearly; includes founding date, key people, mission |
| 5 | Contact page with verifiable information | Manual review | Physical address, phone, email — matches other directory listings |

### Key External Profiles

| # | Signal | Verification Method | Pass Criteria |
|---|--------|-------------------|---------------|
| 6 | Wikidata entry exists | Search wikidata.org | Entry with label, description, key properties, and references |
| 7 | Google Business Profile (if applicable) | Search "[entity] Google Business" | Claimed, verified, complete profile |
| 8 | LinkedIn company/person page | Search LinkedIn | Complete profile matching entity name and description |
| 9 | CrunchBase profile (for companies/products) | Search crunchbase.com | Entry with description, founding info, key people |
| 10 | Primary industry directory listing | Search top 3 industry directories | Listed with correct entity information |

### Branded Search Presence

| # | Signal | Verification Method | Pass Criteria |
|---|--------|-------------------|---------------|
| 11 | Branded search returns correct entity | Google "[entity name]" | Entity's website is #1; Knowledge Panel appears or SERP clearly identifies entity |
| 12 | No disambiguation confusion | Google "[entity name]" | No other prominent entity dominates results for the same name |
| 13 | Branded search volume exists | Check ~~SEO tool | Measurable branded search volume (any amount > 0) |

## Priority 2: Authority Signals (Should-Have)

These signals establish the entity as recognized and authoritative. They separate a "registered entity" from a "known entity."

### Knowledge Graph Depth

| # | Signal | Verification Method | Pass Criteria |
|---|--------|-------------------|---------------|
| 14 | Google Knowledge Panel present | Google "[entity name]" | Knowledge Panel displayed with correct information |
| 15 | Knowledge Panel attributes complete | Review Knowledge Panel | Key attributes filled (founded, CEO, location, industry, etc.) |
| 16 | Knowledge Panel image correct | Review Knowledge Panel | Preferred image displayed |
| 17 | Wikipedia article (or strong notability path) | Search Wikipedia | Article exists, or entity has 3+ independent reliable sources for future article |
| 18 | Wikidata properties complete | Review Wikidata entry | 10+ properties with references |

### Third-Party Validation

| # | Signal | Verification Method | Pass Criteria |
|---|--------|-------------------|---------------|
| 19 | Authoritative media mentions | Google News search for entity | 3+ mentions in recognized publications |
| 20 | Industry awards or recognitions | Search "[entity] award" | At least 1 verifiable award or recognition |
| 21 | Co-citation with established entities | Search for entity alongside competitors | Appears in "X vs Y" comparisons, listicles, or industry roundups |
| 22 | Speaking engagements or publications | Search event/conference sites | Appears as speaker, author, or contributor |
| 23 | Reviews on third-party platforms | Check G2, Trustpilot, Yelp, etc. | Reviews exist with reasonable volume and rating |

### Content Authority

| # | Signal | Verification Method | Pass Criteria |
|---|--------|-------------------|---------------|
| 24 | Topical content depth in target areas | Site search for target topics | 10+ pages covering target topics in depth |
| 25 | Author pages with credentials | Review author pages | Author schema, credentials, sameAs to external profiles |
| 26 | Original research or data published | Review content | At least 1 piece of original data/research cited by others |
| 27 | Entity mentioned in own content naturally | Search site for entity name | Entity name appears contextually (not just in header/footer) |

## Priority 3: AI-Specific Signals (Must-Have for GEO)

These signals specifically help AI systems recognize, understand, and cite the entity.

### AI Recognition

| # | Signal | Verification Method | Pass Criteria |
|---|--------|-------------------|---------------|
| 28 | ChatGPT recognizes entity | Ask "What is [entity]?" | Correct description returned |
| 29 | Perplexity recognizes entity | Ask "What is [entity]?" | Correct description with source citations |
| 30 | Google AI Overview mentions entity | Search branded + topical queries | Entity appears in AI-generated overview |
| 31 | AI description is accurate | Compare AI output to entity's self-description | No factual errors in AI's response |
| 32 | AI associates entity with correct topics | Ask "[entity] expertise areas" | Correct topic associations returned |

### AI Optimization

| # | Signal | Verification Method | Pass Criteria |
|---|--------|-------------------|---------------|
| 33 | Entity definition quotable in first paragraph | Review About page and key pages | Clear, factual, self-contained definition suitable for AI quotation |
| 34 | Factual claims are verifiable | Cross-reference claims with external sources | All claims about entity can be verified via third-party sources |
| 35 | Entity name used consistently | Audit all platforms | Identical name format everywhere (no abbreviations in some places, full name in others) |
| 36 | Content is crawlable by AI systems | Check robots.txt for AI bot access | Not blocking GPTBot, ClaudeBot, or other AI crawlers (unless intentional) |
| 37 | Fresh information available | Check update dates | Key entity pages updated within last 6 months |

## Priority 4: Advanced Signals (Nice-to-Have)

These signals provide marginal gains but demonstrate thoroughness and maturity.

### Extended Knowledge Base Presence

| # | Signal | Verification Method | Pass Criteria |
|---|--------|-------------------|---------------|
| 38 | Multiple language entries in Wikidata | Check Wikidata labels | Labels and descriptions in languages matching target markets |
| 39 | DBpedia entry | Search dbpedia.org | Entry exists (auto-generated from Wikipedia) |
| 40 | Google Knowledge Graph ID known | Search Google Knowledge Graph API | Entity has a kg: identifier |
| 41 | ISNI or VIAF identifier (for persons) | Search isni.org or viaf.org | Identifier exists and links correctly |

### Social Entity Signals

| # | Signal | Verification Method | Pass Criteria |
|---|--------|-------------------|---------------|
| 42 | Social profiles bidirectionally linked | Check website links to social AND social links to website | Both directions verified on all platforms |
| 43 | Consistent entity description across social | Compare bios on all platforms | Same core description, adapted for platform length limits |
| 44 | Social engagement demonstrates real audience | Review engagement metrics | Engagement patterns consistent with genuine audience (not bot-like) |

### Technical Entity Signals

| # | Signal | Verification Method | Pass Criteria |
|---|--------|-------------------|---------------|
| 45 | Entity homepage has strong backlink profile | Check ~~link database | Homepage DR/DA above industry median |
| 46 | Branded anchor text in backlinks | Analyze anchor text distribution | Entity name appears naturally in inbound link anchor text |
| 47 | Entity subdomain consistency | Check all subdomains | Same entity schema and branding across all subdomains |

## How to Use This Checklist

Work through signals by priority tier. For each signal, mark status as ✅ (present and correct), ⚠️ (present but incomplete), or ❌ (absent). Focus on completing each priority tier before moving to the next.

### Priority Action Matrix

| Current State | Focus Area | Expected Timeline |
|--------------|-----------|-------------------|
| Most Priority 1 signals ❌ | Priority 1 foundation signals only | 2-4 weeks |
| Priority 1 mostly ✅, Priority 2 mixed | Priority 2 authority signals | 1-2 months |
| Priority 1-2 mostly ✅ | Priority 3 AI-specific signals | 2-3 months |
| Priority 1-3 mostly ✅ | Selective Priority 4 for completeness | Ongoing |
| All tiers mostly ✅ | Maintenance + quarterly re-audit | Quarterly review |
