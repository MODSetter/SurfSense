---
name: meeting-prep
description: Pull together briefing materials before a scheduled meeting
allowed-tools: search_surfsense_docs, web_search, scrape_webpage, read_file
---

# Meeting preparation

## When to use this skill
The user mentions an upcoming meeting, call, or interview and asks you to "prep", "brief me", "pull background", or "what do I need to know about X before tomorrow".

## Output structure
Always produce these sections (omit any with no signal — don't pad):

1. **Attendees & context** — who's in the room, their roles, what they care about. Pull from KB notes about prior interactions; supplement with public profile facts via `web_search` when names or companies are unfamiliar.
2. **Open threads** — outstanding action items, unresolved decisions, last-mentioned blockers from prior conversation history.
3. **Recent moves** — within the last 30 days: relevant launches, hires, news. Cite KB chunks when present, otherwise external sources.
4. **Suggested questions** — 3-5 questions the user could ask, tailored to the open threads and the attendees' likely priorities.

## Source ordering
- Always check the user's KB **first** for prior meeting notes, internal docs, or Slack threads about these attendees.
- Only fall back to `web_search` for *publicly verifiable* facts — never to fabricate a participant's preferences or relationships.
