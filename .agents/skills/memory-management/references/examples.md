# Memory Management Examples

Detailed examples showing memory management in action.

---

## Example 1: Update Rankings for Hero Keywords

**User**: "Update rankings for our hero keywords"

**Assistant**:

```markdown
I'll update rankings for your hero keywords. Let me check the hot cache for the list.

[Reads CLAUDE.md, finds Hero Keywords section:]
- keyword research tools (currently #15, target #5)
- best seo software (currently #23, target #10)
- free backlink checker (currently #8, target #3)
- content optimization guide (currently #12, target #5)
- technical seo audit (currently #18, target #8)

[If ~~SEO tool connected: runs automated ranking check]
[If manual: asks user for current rankings]

---

## Ranking Update - December 15, 2024

| Keyword | Previous | Current | Change | Target | Status |
|---------|----------|---------|--------|--------|--------|
| keyword research tools | #15 | #12 | up 3 | #5 | Improving |
| best seo software | #23 | #24 | down 1 | #10 | Stable |
| free backlink checker | #8 | #6 | up 2 | #3 | Near target |
| content optimization guide | #12 | #11 | up 1 | #5 | Improving |
| technical seo audit | #18 | #16 | up 2 | #8 | Improving |

### Notable Changes
- **free backlink checker** moved to #6 (only 3 positions from target!)
- **keyword research tools** gained 3 positions (strong movement)
- All other keywords showing stable or positive movement

### Updated Files
1. CLAUDE.md -> Hero Keywords table updated with current ranks
2. memory/monitoring/rank-history/2024-12-15-ranks.csv -> New row added:
   `2024-12-15,keyword research tools,12,best seo software,24,free backlink checker,6,...`

### Recommendations
1. Push additional content/backlinks to "free backlink checker" pages to hit #3 target
2. Investigate why "keyword research tools" suddenly gained 3 positions (replicate success)
3. Monitor "best seo software" for any negative trends

Hot cache refreshed. Next ranking check recommended: December 22, 2024.
```

---

## Example 2: Glossary Lookup

**User**: "What does 'quick wins' mean in our project?"

**Assistant**:

```markdown
Let me look that up in the project memory.

[Step 1: Check CLAUDE.md -> not found]
[Step 2: Check memory/glossary.md -> found!]

From your project glossary:

**Quick Wins**
- **Definition**: Low-difficulty, high-value target keywords
- **Keyword Count**: 25 keywords
- **Context**: This segment includes keywords where you can achieve page 1 rankings within 30-60 days due to low competition, despite having decent search volume

According to your memory files, your current quick wins are stored in:
`memory/research/keywords/long-tail-keywords.md` (tagged with "quick-win" label)

Would you like me to show you the current list of quick win keywords?
```

---

## Example 3: Initialize Memory for New Project

**User**: "Set up memory for a new e-commerce site selling outdoor gear"

**Assistant**:

```markdown
I'll set up the two-layer memory system for your outdoor gear e-commerce site.

## Creating Directory Structure

[Creates: memory/glossary.md, memory/research/, memory/content/, memory/monitoring/, etc.]

## CLAUDE.md (Hot Cache) - Initial Setup

I'll need some information to populate the hot cache:

1. **Target Keywords**: What are your top 10 hero keywords?
   (e.g., "hiking backpacks", "camping tents", "outdoor clothing")

2. **Primary Competitors**: Who are your top 3-5 competitors?
   (e.g., rei.com, backcountry.com, moosejaw.com)

3. **Current Metrics** (if available):
   - Domain authority?
   - Current organic traffic?
   - Any existing rankings?

4. **Active Initiatives**:
   - Are you launching a new category?
   - Running a content campaign?
   - Focusing on any specific product line?

5. **Project Terminology**:
   - Any internal product names or abbreviations?
   - How do you segment your keyword strategy?

Please provide what you have, and I'll create your initial CLAUDE.md and glossary. We can start with basics and enrich as we gather more data.

---

Once you provide this information, I'll generate:
- CLAUDE.md with your initial hot cache
- memory/glossary.md with project terminology
- memory/research/keywords/ structure with placeholder files
- memory/research/competitors/ with initial competitor list
- memory/content/calendar/active-calendar.md for Q1 2025

After setup, you can use commands like:
- "Update rankings for hero keywords"
- "Add new competitor [domain]"
- "Promote [keyword] to hot cache"
- "Archive campaigns from Q3 2024"
```
