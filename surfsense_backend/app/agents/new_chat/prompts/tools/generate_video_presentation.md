
- generate_video_presentation: Generate a video presentation from provided content.
  - Use this when the user asks to create a video, presentation, slides, or slide deck.
  - Trigger phrases: "give me a presentation", "create slides", "generate a video", "make a slide deck", "turn this into a presentation"
  - Args:
    - source_content: The text content to turn into a presentation. The more detailed, the better.
    - video_title: Optional title (default: "SurfSense Presentation")
    - user_prompt: Optional style instructions (e.g., "Make it technical and detailed")
  - After calling this tool, inform the user that generation has started and they will see the presentation when it's ready.
