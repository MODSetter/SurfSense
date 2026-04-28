---
name: report-writing
description: How to scope, draft, and revise a Markdown report artifact via generate_report
allowed-tools: generate_report, search_surfsense_docs, read_file
---

# Report writing

## When to use this skill
The user explicitly requests a deliverable: "write a report on …", "draft a memo", "produce a brief", "expand the previous report". A creation or modification verb pointed at an artifact is required (see `generate_report`'s when-to-call rules).

## Decision flow
1. **Source strategy.** Decide which `source_strategy` fits:
   - `conversation` — substantive Q&A on the topic already in chat.
   - `kb_search` — fresh topic; supply 1–5 precise `search_queries`.
   - `auto` — partial conversation context; let the tool fall back.
   - `provided` — verbatim source text only.
2. **Style.** Default to `report_style="detailed"` unless the user explicitly asks for "brief", "one page", "500 words".
3. **Revisions.** When modifying an existing report from this conversation, set `parent_report_id` and put the change list in `user_instructions` ("add carbon-capture section", "tighten conclusion").
4. **Never paste the report back into chat** after `generate_report` returns — confirm and let the artifact card render itself.

## Hooks for KB-only mode
If `kb_search`/`auto` returns no results, do **not** silently switch to general knowledge. Surface the gap in your confirmation message.
