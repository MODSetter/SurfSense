# Promotion and Demotion Rules

Detailed triggers and actions for moving items between the hot cache (CLAUDE.md) and cold storage (memory/ subdirectories).

## Promotion Logic

**Promote to Hot Cache when:**

### Keyword promotion triggers:
- Keyword referenced in 3+ conversations within 7 days
- Keyword showing significant movement (5+ position change)
- Keyword targeted in new active campaign
- Keyword suddenly driving traffic spike

### Competitor promotion triggers:
- Competitor mentioned in 3+ recent analyses
- Competitor showing aggressive SEO activity
- Competitor launching competing content

### Metric promotion triggers:
- Metric requested frequently for reporting
- Metric showing anomalous behavior
- Metric tied to active priority/campaign

**Promotion action:**
```markdown
1. Add item to relevant section in CLAUDE.md
2. Add note: "Promoted [date] - [reason]"
3. Keep detailed data in cold storage
4. Set reminder to review in 30 days
```

## Demotion Logic

**Demote to Cold Storage when:**

### Keyword demotion triggers:
- Not referenced in 30+ days
- Target rank achieved and stable for 60+ days
- Keyword no longer in active strategy
- Keyword replaced by higher-priority target

### Competitor demotion triggers:
- No significant activity in 60+ days
- Fell out of top 5 competitors by relevance
- No longer targeting same keywords

### Campaign demotion triggers:
- Campaign completed 30+ days ago
- Campaign cancelled or postponed indefinitely

**Demotion action:**
```markdown
1. Remove from CLAUDE.md
2. Archive full data in memory/[category]/archive/
3. Add line to CLAUDE.md: "Last reviewed [category]: [date]"
4. Keep 1-line summary if historically significant
```
