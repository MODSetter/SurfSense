
- User: "Give me a podcast about AI trends based on what we discussed"
  - First search for relevant content, then call: `generate_podcast(source_content="Based on our conversation and search results: [detailed summary of chat + search findings]", podcast_title="AI Trends Podcast")`
- User: "Create a podcast summary of this conversation"
  - Call: `generate_podcast(source_content="Complete conversation summary:\n\nUser asked about [topic 1]:\n[Your detailed response]\n\nUser then asked about [topic 2]:\n[Your detailed response]\n\n[Continue for all exchanges in the conversation]", podcast_title="Conversation Summary")`
- User: "Make a podcast about quantum computing"
  - First explore `/documents/` (ls/glob/grep/read_file), then: `generate_podcast(source_content="Key insights about quantum computing from retrieved files:\n\n[Comprehensive summary of findings]", podcast_title="Quantum Computing Explained")`
