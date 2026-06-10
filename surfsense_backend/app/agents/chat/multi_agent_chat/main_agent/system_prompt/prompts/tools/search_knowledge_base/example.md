<example>
user: "What did our Q3 planning doc say about hiring?"
→ search_knowledge_base(query="Q3 planning hiring headcount plan")
(Answer from the returned snippets with a citation; if you need the full
document, task the knowledge_base specialist with the returned path.)
</example>

<example>
user: "Summarize my notes on the Acme migration."
→ search_knowledge_base(query="Acme migration notes")
→ task(subagent_type="knowledge_base", description="Read <path> and return a
detailed summary of the Acme migration plan, risks, and timeline.")
</example>
