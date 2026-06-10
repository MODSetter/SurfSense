<example>
user: "Save these meeting notes to my KB: …"
→ task(subagent_type="knowledge_base", description="Save the notes below to
  a new document under /documents/notes/. Pick a sensible title and folder;
  tell me the path you used.\n\n<notes>…</notes>")
</example>

<example>
user: "What did Maya say about the Q2 roadmap in Slack last week?"
→ task(subagent_type="slack", description="Find messages from Maya about
  the Q2 roadmap from the past week. Return the most relevant quotes with
  channel and timestamp.")
</example>

<example>
user: "Find my Q2 roadmap and summarise the milestones."
→ task(subagent_type="knowledge_base", description="Locate the Q2 roadmap
  document under /documents and summarise its milestones. Use glob or grep
  if the path isn't obvious from the workspace tree.")
</example>
