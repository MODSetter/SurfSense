
- generate_podcast: Generate an audio podcast from provided content.
  - Use this when the user asks to create, generate, or make a podcast.
  - Trigger phrases: "give me a podcast about", "create a podcast", "generate a podcast", "make a podcast", "turn this into a podcast"
  - Args:
    - source_content: The text content to convert into a podcast. This MUST be comprehensive and include:
      * If discussing the current conversation: Include a detailed summary of the FULL chat history (all user questions and your responses)
      * If based on knowledge base search: Include the key findings and insights from the search results
      * You can combine both: conversation context + search results for richer podcasts
      * The more detailed the source_content, the better the podcast quality
    - podcast_title: Optional title for the podcast (default: "SurfSense Podcast")
    - user_prompt: Optional instructions for podcast style/format (e.g., "Make it casual and fun")
  - Returns: A task_id for tracking. The podcast will be generated in the background.
  - IMPORTANT: Only one podcast can be generated at a time. If a podcast is already being generated, the tool will return status "already_generating".
  - After calling this tool, inform the user that podcast generation has started and they will see the player when it's ready (takes 3-5 minutes).
