---
name: kb-research
description: Structured approach to finding and synthesizing information from the user's knowledge base
allowed-tools: search_surfsense_docs, scrape_webpage, read_file, ls_tree, grep, web_search
---

# Knowledge-base research

## When to use this skill
- The user asks "find/look up/research" something specifically inside their knowledge base.
- The user references documents, notes, repos, or connector data they expect to exist already.
- A multi-document synthesis is required (e.g., "summarize what we've discussed about X across all my notes").

## Plan
1. Decompose the user's question into 2-4 specific, citation-worthy sub-questions.
2. For each sub-question, run **one** targeted KB search (focused on terms the user would have written, not synonyms). Open the most relevant 2-3 documents fully via `read_file` if their excerpts are too short.
3. Use `grep` to find supporting passages in long files instead of re-reading them end to end.
4. Cite every claim with `[citation:chunk_id]` exactly as the chunk tag specifies.

## What good output looks like
- Short paragraphs with inline citations.
- Quoted phrases when wording matters.
- An explicit "Not found in your knowledge base" callout when a sub-question has no support — never fabricate.
