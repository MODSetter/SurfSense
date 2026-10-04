from modules.plugins.runner.job import run
from shared.queue import plugins_queue


# No retries: what a plugin wrote through the API stays, so a second go would
# write it twice.
@plugins_queue.task()
def run_plugin(run_id: int) -> None:
    """Run one action of a plugin as its own process, and record how it ended."""
    run(run_id)
