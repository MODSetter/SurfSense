# Example: Entity Optimization Report

Full example output for an entity audit request.

**User**: "Audit entity presence for CloudMetrics, our B2B SaaS analytics platform at cloudmetrics.io"

**Output**:

```markdown
## Entity Optimization Report

### Entity Profile

**Entity Name**: CloudMetrics
**Entity Type**: Organization (B2B SaaS)
**Primary Domain**: cloudmetrics.io
**Target Topics**: analytics platform, business intelligence, enterprise analytics

### AI Entity Resolution Test

Queries tested with results reported by user:

| Query | Result | Assessment |
|-------|--------|------------|
| "What is CloudMetrics?" | Described as "an analytics tool" with no further detail | Partial recognition -- generic description, no mention of B2B focus or key features |
| "Best analytics platforms for enterprises" | CloudMetrics not mentioned in any AI response | Not recognized as a player in the enterprise analytics space |
| "CloudMetrics vs Datadog" | Correctly identified as a competitor to Datadog, but feature comparison was incomplete and partially inaccurate | Partial -- entity is associated with the right category but attributes are thin |
| "Who founded CloudMetrics?" | No answer found by any AI system tested | Entity leadership not present in AI knowledge bases |

### Entity Health Summary

| Signal Category | Status | Key Findings |
|-----------------|--------|--------------|
| Knowledge Graph | Missing | No Wikidata entry exists; no Google Knowledge Panel triggers for branded queries |
| Structured Data | Partial | Organization schema present on homepage with name, url, and logo; missing Person schema for CEO and leadership team; no sameAs links to external profiles |
| Web Presence | Strong | Consistent NAP across LinkedIn, Twitter/X, G2, and Crunchbase; social profiles link back to cloudmetrics.io; branded search returns owned properties in top 5 |
| Content-Based | Partial | About page exists but opens with marketing copy rather than an entity-defining statement; no dedicated author pages for leadership |
| Third-Party | Partial | Listed on G2 and Crunchbase; 2 industry publication mentions found; no awards or analyst coverage |
| AI-Specific | Weak | AI systems have only surface-level awareness; entity definition is not quotable from any authoritative source |

### Top 3 Priority Actions

1. **Create Wikidata entry** with key properties: instance of (P31: business intelligence software company), official website (P856: cloudmetrics.io), inception (P571), country (P17)
   - Impact: High | Effort: Low
   - Why: Wikidata is the foundational knowledge base that feeds Google Knowledge Graph, Bing, and AI training pipelines; without it, the entity cannot be formally resolved

2. **Add Person schema for leadership team** on the About/Team page, including name, jobTitle, sameAs links to LinkedIn profiles, and worksFor pointing to the Organization entity
   - Impact: High | Effort: Low
   - Why: Addresses the "Who founded CloudMetrics?" gap directly; Person schema for key people creates bidirectional entity associations that strengthen organizational identity

3. **Build Wikipedia notability through independent press coverage** -- target 3-5 articles in industry publications (TechCrunch, VentureBeat, Analytics India Magazine) that mention CloudMetrics by name with verifiable claims
   - Impact: High | Effort: High
   - Why: Wikipedia notability requires coverage in independent reliable sources; press mentions simultaneously feed AI training data, build third-party entity signals, and create the citation foundation for a future Wikipedia article

### Cross-Reference

- **CORE-EEAT**: A07 (Knowledge Graph Presence) scored Fail, A08 (Entity Consistency) scored Pass -- entity optimization should focus on knowledge base gaps rather than consistency
- **CITE**: I-dimension weakest area is I01 (Knowledge Graph Presence) -- completing Wikidata entry and earning Knowledge Panel directly improves domain identity score
```
