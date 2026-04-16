# Update Triggers & Cross-Skill Integration

Systematic memory update procedures triggered by specific events, plus integration points with other SEO skills.

## Update Triggers

After specific events, update memory systematically:

### After Ranking Check
```markdown
1. Update CLAUDE.md -> Hero Keywords table (current ranks)
2. Save a dated snapshot to memory/monitoring/rank-history/YYYY-MM-DD-ranks.csv
3. Note any keywords with significant movement
4. Update "Last Metrics Update" date in CLAUDE.md
5. If hero keyword moves +/-5 positions, create alert note
```

### After Competitor Analysis
```markdown
1. Update CLAUDE.md -> Primary Competitors section (DA, position vs. them)
2. Save full report to memory/research/competitors/YYYY-MM-DD-analysis.md
3. Update competitor overview notes in memory/research/competitors/
4. Note new competitor strategies in hot cache
```

### After Audit (Technical/Content/Backlink)
```markdown
1. Save full report to memory/audits/[type]/YYYY-MM-DD-[audit-name].md
2. Extract top 3-5 action items -> CLAUDE.md Current Optimization Priorities
3. Update Key Metrics Snapshot if audit includes metrics
4. Create campaign entry if audit spawns new initiative
```

### After Monthly/Quarterly Report
```markdown
1. Save report to memory/monitoring/reports/[period]/YYYY-MM-report.md
2. Update all metrics in CLAUDE.md Key Metrics Snapshot
3. Review hot cache -> demote stale items
4. Update campaign statuses
5. Archive completed campaigns
```

## Archive Management

### Monthly Archive Routine
```markdown
1. Review CLAUDE.md for items not referenced in 30 days
2. Move stale items to appropriate cold storage
3. Create monthly snapshot: memory/monitoring/snapshots/YYYY-MM-CLAUDE.md
4. Compress old rank-history exports (keep recent snapshots easiest to access)
5. Update glossary with new terms from the month
```

### Quarterly Archive Routine
```markdown
1. Review entire cold storage structure
2. Compress files older than 6 months
3. Create quarterly summary report
4. Update project timeline in glossary
5. Audit all active campaigns -> archive completed ones
```

## Cross-Skill Memory Integration

This skill coordinates with other SEO skills:

### When keyword-research runs:
- Add discovered keywords to memory/research/keywords/
- Promote top opportunities to CLAUDE.md if high-value
- Update glossary if new terminology emerges

### When rank-tracker runs:
- Update memory/monitoring/rank-history/
- Refresh CLAUDE.md Hero Keywords table
- Flag significant movements for hot cache notes

### When competitor-analysis runs:
- Update competitor files in memory/research/competitors/
- Refresh CLAUDE.md Primary Competitors section
- Add new competitors if they outrank current top 5

### When content-gap-analysis runs:
- Store full findings in memory/research/content-gaps/
- Promote gap opportunities to CLAUDE.md priorities
- Update memory/content/calendar/ with recommended topics

### When seo-content-writer produces content:
- Log to memory/content/published/YYYY-MM-DD-[slug].md
- Track target keyword and publish date
- Set reminder to check performance in 30 days

### When content-quality-auditor runs:
- Save full report to `memory/audits/content/YYYY-MM-DD-core-eeat-[page-slug].md`
- Update CLAUDE.md Key Metrics with latest score
- If score < 60 (Poor/Low), flag in Active Campaigns section
- Track dimension scores for trend analysis

### When domain-authority-auditor runs:
- Save full report to memory/audits/domain/YYYY-MM-DD-cite-audit.md
- Update CITE Score in CLAUDE.md Key Metrics Snapshot
- Note veto item status and dimension scores
- Compare against previous CITE audit if available
