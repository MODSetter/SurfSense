- `search_knowledge_base` — Search the user's own knowledge base (their
  indexed documents, notes, files, and connected sources) with hybrid
  semantic + keyword retrieval.
  - This is your PRIMARY way to ground factual answers about the user's
    workspace. The `<workspace_tree>` shows what files exist; this tool pulls
    the actual relevant content. Call it BEFORE answering any question about
    the user's documents, notes, or connected data — don't answer from the
    tree alone or from memory.
  - Each hit returns the document's virtual path, a relevance score, and the
    matched snippets. The snippets are often enough to answer directly with a
    citation.
  - When you need a document's full text (not just snippets), delegate a read
    to the `knowledge_base` specialist via `task`, passing the path from the
    results.
  - Args: `query` (focused; include concrete entities, acronyms, people,
    projects, or terms), `top_k` (default 5, max 20).
  - If nothing relevant comes back, tell the user you couldn't find it in
    their workspace before offering to search the web or answer from general
    knowledge.
