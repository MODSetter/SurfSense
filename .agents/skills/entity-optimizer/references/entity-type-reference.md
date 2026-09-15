# Entity Type Reference

Reference tables for entity types, key signals, and disambiguation strategies.

## Entity Types and Key Signals

| Entity Type | Primary Signals | Secondary Signals | Key Schema |
|-------------|----------------|-------------------|------------|
| **Person** | Author pages, social profiles, publication history | Speaking, awards, media mentions | Person, ProfilePage |
| **Organization** | Registration records, Wikidata, industry listings | Press coverage, partnerships, awards | Organization, Corporation |
| **Brand** | Trademark, branded search volume, social presence | Reviews, brand mentions, visual identity | Brand, Organization |
| **Product** | Product pages, reviews, comparison mentions | Awards, expert endorsements, market share | Product, SoftwareApplication |
| **Creative Work** | Publication record, citations, reviews | Awards, adaptations, cultural impact | CreativeWork, Book, Movie |
| **Event** | Event listings, press coverage, social buzz | Sponsorships, speaker profiles, attendance | Event |

## Disambiguation Strategy by Situation

| Situation | Strategy |
|-----------|----------|
| **Common name, unique entity** | Strengthen all signals; let signal volume resolve ambiguity |
| **Name collision with larger entity** | Add qualifier consistently (e.g., "Acme Software" not just "Acme"); use sameAs extensively; build topic-specific authority that differentiates |
| **Name collision with similar entity** | Geographic, industry, or product qualifiers; ensure Schema @id is unique and consistent; prioritize Wikidata disambiguation |
| **Abbreviation/acronym conflict** | Prefer full name in structured data; use abbreviation only in contexts where entity is already established |
| **Merged or renamed entity** | Redirect old entity signals; update all structured data; create explicit "formerly known as" content; update Wikidata |
