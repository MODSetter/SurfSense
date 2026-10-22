from modules.documents.web_sources.background_pull.pull import pull
from shared.queue import plugins_queue


# No retries: a pull that failed says why, and the user's Retry pulls again.
@plugins_queue.task()
def pull_web_source(document_id: int) -> None:
    """Pull one link through its plugin, write it as the note's text, then index it."""
    pull(document_id)
