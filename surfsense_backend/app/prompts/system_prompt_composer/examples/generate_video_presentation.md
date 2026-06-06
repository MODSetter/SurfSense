
- User: "Give me a presentation about AI trends based on what we discussed"
  - First search for relevant content, then call: `generate_video_presentation(source_content="Based on our conversation and search results: [detailed summary of chat + search findings]", video_title="AI Trends Presentation")`
- User: "Create slides summarizing this conversation"
  - Call: `generate_video_presentation(source_content="Complete conversation summary:\n\nUser asked about [topic 1]:\n[Your detailed response]\n\nUser then asked about [topic 2]:\n[Your detailed response]\n\n[Continue for all exchanges in the conversation]", video_title="Conversation Summary")`
- User: "Make a video presentation about quantum computing"
  - First explore `/documents/` (ls/glob/grep/read_file), then: `generate_video_presentation(source_content="Key insights about quantum computing from retrieved files:\n\n[Comprehensive summary of findings]", video_title="Quantum Computing Explained")`
