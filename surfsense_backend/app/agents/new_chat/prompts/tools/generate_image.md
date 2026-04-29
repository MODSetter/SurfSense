
- generate_image: Generate images from text descriptions using AI image models.
  - Use this when the user asks you to create, generate, draw, design, or make an image.
  - Trigger phrases: "generate an image of", "create a picture of", "draw me", "make an image", "design a logo", "create artwork"
  - Args:
    - prompt: A detailed text description of the image to generate. Be specific about subject, style, colors, composition, and mood.
    - n: Number of images to generate (1-4, default: 1)
  - Returns: A dictionary with the generated image metadata. The image will automatically be displayed in the chat.
  - IMPORTANT: Write a detailed, descriptive prompt for best results. Don't just pass the user's words verbatim -
    expand and improve the prompt with specific details about style, lighting, composition, and mood.
  - If the user's request is vague (e.g., "make me an image of a cat"), enhance the prompt with artistic details.
