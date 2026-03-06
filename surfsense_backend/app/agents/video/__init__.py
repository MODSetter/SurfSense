"""Video generation package.

Public API:
  generate_video_script() — LLM structured output → VideoInput JSON
"""

from app.agents.video.script_generator import generate_video_script

__all__ = ["generate_video_script"]
