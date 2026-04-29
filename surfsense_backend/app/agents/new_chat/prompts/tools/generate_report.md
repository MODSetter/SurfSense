
- generate_report: Generate or revise a structured Markdown report artifact.
  - WHEN TO CALL THIS TOOL — the message must contain a creation or modification VERB directed at producing a deliverable:
    * Creation verbs: write, create, generate, draft, produce, summarize into, turn into, make
    * Modification verbs: revise, update, expand, add (a section), rewrite, make (it shorter/longer/formal)
    * Example triggers: "generate a report about...", "write a document on...", "add a section about budget", "make the report shorter", "rewrite in formal tone"
  - WHEN NOT TO CALL THIS TOOL (answer in chat instead):
    * Questions or discussion about the report: "What can we add?", "What's missing?", "Is the data accurate?", "How could this be improved?"
    * Suggestions or brainstorming: "What other topics could be covered?", "What else could be added?", "What would make this better?"
    * Asking for explanations: "Can you explain section 2?", "Why did you include that?", "What does this part mean?"
    * Quick follow-ups or critiques: "Is the conclusion strong enough?", "Are there any gaps?", "What about the competitors?"
    * THE TEST: Does the message contain a creation/modification VERB (from the list above) directed at producing or changing a deliverable? If NO verb → answer conversationally in chat. Do NOT assume the user wants a revision just because a report exists in the conversation.
  - IMPORTANT FORMAT RULE: Reports are ALWAYS generated in Markdown.
  - Args:
    - topic: Short title for the report (max ~8 words).
    - source_content: The text content to base the report on.
      * For source_strategy="conversation" or "provided": Include a comprehensive summary of the relevant content.
      * For source_strategy="kb_search": Can be empty or minimal — the tool handles searching internally.
      * For source_strategy="auto": Include what you have; the tool searches KB if it's not enough.
    - source_strategy: Controls how the tool collects source material. One of:
      * "conversation" — The conversation already contains enough context (prior Q&A, discussion, pasted text, scraped pages). Pass a thorough summary as source_content.
      * "kb_search" — The tool will search the knowledge base internally. Provide search_queries with 1-5 targeted queries.
      * "auto" — Use source_content if sufficient, otherwise fall back to internal KB search using search_queries.
      * "provided" — Use only what is in source_content (default, backward-compatible).
    - search_queries: When source_strategy is "kb_search" or "auto", provide 1-5 specific search queries for the knowledge base. These should be precise, not just the topic name repeated.
    - report_style: Controls report depth. Options: "detailed" (DEFAULT), "deep_research", "brief".
      Use "brief" ONLY when the user explicitly asks for a short/concise/one-page report (e.g., "one page", "keep it short", "brief report", "500 words"). Default to "detailed" for all other requests.
    - user_instructions: Optional specific instructions (e.g., "focus on financial impacts", "include recommendations"). When revising (parent_report_id set), describe WHAT TO CHANGE. If the user mentions a length preference (e.g., "one page", "500 words", "2 pages"), include that VERBATIM here AND set report_style="brief".
    - parent_report_id: Set this to the report_id from a previous generate_report result when the user wants to MODIFY an existing report. Do NOT set it for new reports or questions about reports.
  - Returns: A dictionary with status "ready" or "failed", report_id, title, and word_count.
  - The report is generated immediately in Markdown and displayed inline in the chat.
  - Export/download formats (PDF, DOCX, HTML, LaTeX, EPUB, ODT, plain text) are produced from the generated Markdown report.
  - SOURCE STRATEGY DECISION (HIGH PRIORITY — follow this exactly):
    * If the conversation already has substantive Q&A / discussion on the topic → use source_strategy="conversation" with a comprehensive summary as source_content.
    * If the user wants a report on a topic not yet discussed → use source_strategy="kb_search" with targeted search_queries.
    * If you have some content but might need more → use source_strategy="auto" with both source_content and search_queries.
    * When revising an existing report (parent_report_id set) and the conversation has relevant context → use source_strategy="conversation". The revision will use the previous report content plus your source_content.
    * NEVER run a separate KB lookup step and then pass those results to generate_report. The tool handles KB search internally.
  - AFTER CALLING THIS TOOL: Do NOT repeat, summarize, or reproduce the report content in the chat. The report is already displayed as an interactive card that the user can open, read, copy, and export. Simply confirm that the report was generated (e.g., "I've generated your report on [topic]. You can view the Markdown report now, and export it in various formats from the card."). NEVER write out the report text in the chat.
