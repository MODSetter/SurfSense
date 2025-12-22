"""
Legacy podcast task for old chat system.

NOTE: The old Chat model has been removed. This module is kept for backwards
compatibility but the generate_chat_podcast function will raise an error
if called. Use generate_content_podcast_task in celery_tasks/podcast_tasks.py
for new-chat podcast generation instead.
"""

from app.db import Podcast  # noqa: F401 - imported for backwards compatibility


async def generate_chat_podcast(*args, **kwargs):
    """
    Legacy function for generating podcasts from old chat system.

    This function is deprecated as the old Chat model has been removed.
    Use generate_content_podcast_task for new-chat podcast generation.
    """
    raise NotImplementedError(
        "generate_chat_podcast is deprecated. The old Chat model has been removed. "
        "Use generate_content_podcast_task for podcast generation from new-chat."
    )
