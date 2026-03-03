"""Video generation package.

Public API:
  generate_video() — one-shot pipeline: LLM → sandbox → MP4
"""

from app.agents.video.pipeline import generate_video

__all__ = ["generate_video"]
