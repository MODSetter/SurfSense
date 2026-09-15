# Knowledge Panel & Wikidata Optimization Guide

Detailed instructions for Knowledge Panel optimization, Wikidata entry management, and AI entity resolution.

## Knowledge Panel Optimization

### Claiming and Editing

1. **Google Knowledge Panel**: Claim via Google's verification process (search for entity -> click "Claim this knowledge panel")
2. **Bing Knowledge Panel**: Driven by Wikidata and LinkedIn -- update those sources
3. **AI Knowledge**: Driven by training data -- ensure authoritative sources describe entity correctly

### Common Knowledge Panel Issues

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| No panel appears | Entity not in Knowledge Graph | Build Wikidata entry + structured data + authoritative mentions |
| Wrong image | Image sourced from incorrect page | Update Wikidata image; ensure preferred image on About page and social profiles |
| Wrong description | Description pulled from wrong source | Edit Wikidata description; ensure About page has clear entity description in first paragraph |
| Missing attributes | Incomplete structured data | Add properties to Schema.org markup and Wikidata entry |
| Wrong entity shown | Disambiguation failure | Strengthen unique signals; add qualifiers; resolve Wikidata disambiguation |
| Outdated info | Source data not updated | Update Wikidata, About page, and all profile pages |

## Wikidata Best Practices

### Creating a Wikidata Entry

1. **Check notability**: Entity must have at least one authoritative reference
2. **Create item**: Add label, description, and aliases in relevant languages
3. **Add statements**: instance of, official website, social media links, founding date, founders, industry
4. **Add identifiers**: official website (P856), social media IDs, CrunchBase ID, ISNI, VIAF
5. **Add references**: Every statement should have a reference to an authoritative source

**Important**: Wikipedia's Conflict of Interest (COI) policy prohibits individuals and organizations from creating or editing articles about themselves. Instead of directly editing Wikipedia: (1) Focus on building notability through independent reliable sources (press coverage, industry publications, academic citations); (2) If you believe a Wikipedia article is warranted, consider engaging an independent Wikipedia editor through the Requested Articles process; (3) Ensure all claims about the entity are verifiable through third-party sources before any Wikipedia involvement.

### Key Wikidata Properties by Entity Type

| Property | Code | Person | Org | Brand | Product |
|----------|------|:------:|:---:|:-----:|:-------:|
| instance of | P31 | human | organization type | brand | product type |
| official website | P856 | yes | yes | yes | yes |
| occupation / industry | P106/P452 | yes | yes | -- | -- |
| founded by | P112 | -- | yes | yes | -- |
| inception | P571 | -- | yes | yes | yes |
| country | P17 | yes | yes | -- | -- |
| social media | various | yes | yes | yes | yes |
| employer | P108 | yes | -- | -- | -- |
| developer | P178 | -- | -- | -- | yes |

## AI Entity Optimization

### How AI Systems Resolve Entities

```
User query -> Entity extraction -> Entity resolution -> Knowledge retrieval -> Answer generation
```

AI systems follow this pipeline:
1. **Extract** entity mentions from the query
2. **Resolve** each mention to a known entity (or fail -> "I'm not sure")
3. **Retrieve** associated knowledge about the entity
4. **Generate** response citing sources that confirmed the entity's attributes

### Signals AI Systems Use for Entity Resolution

| Signal Type | What AI Checks | How to Optimize |
|-------------|---------------|-----------------|
| **Training data presence** | Was entity in pre-training corpus? | Get mentioned in high-quality, widely-crawled sources |
| **Retrieval augmentation** | Does entity appear in live search results? | Strong SEO presence for branded queries |
| **Structured data** | Can entity be matched to Knowledge Graph? | Complete Wikidata + Schema.org |
| **Contextual co-occurrence** | What topics/entities appear alongside? | Build consistent topic associations across content |
| **Source authority** | Are sources about entity trustworthy? | Get mentioned by authoritative, well-known sources |
| **Recency** | Is information current? | Keep all entity profiles and content updated |

### Entity-Specific GEO Tactics

1. **Define clearly**: First paragraph of About page and key pages should define the entity in a way AI can quote directly
2. **Be consistent**: Use identical entity description across all platforms
3. **Build associations**: Create content that explicitly connects entity to target topics
4. **Earn mentions**: Third-party authoritative mentions are stronger entity signals than self-description
5. **Stay current**: Outdated entity information causes AI to lose confidence and stop citing
