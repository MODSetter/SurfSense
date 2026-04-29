---
name: slack-summary
description: Distill a Slack channel or thread into actionable summary
allowed-tools: search_surfsense_docs
---

# Slack summarization

## When to use this skill
The user asks to summarize Slack ("what happened in #eng-platform this week", "what did Alice say about the launch", "catch me up on the design channel").

## Required inputs
Confirm before searching:
- **Which channel(s) or thread(s)?** Don't guess if ambiguous.
- **What time window?** Default to the last 7 days when not specified, but say so.

## Output shape
Produce three concise sections:
1. **Key decisions** — explicit choices that were made, with the deciding message cited.
2. **Open questions** — things asked but not answered, with the asking message cited.
3. **Action items** — `@mention` who owes what by when, *only if explicitly stated*. Don't invent assignees.

## What not to do
- Never produce a chronological play-by-play of every message — distill.
- Never quote private messages without flagging them as such.
- If the channel was empty in the time window, say so — don't fabricate filler.
