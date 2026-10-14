from contextlib import suppress

import psutil

# How long a plugin has to exit after being asked, before it is killed.
GRACE_SECONDS = 5


def stop_process_tree(pid: int) -> None:
    """Ask the plugin and every process it started to exit, then kill what did not."""
    try:
        root = psutil.Process(pid)
        tree = [root, *root.children(recursive=True)]
    except psutil.NoSuchProcess:
        return
    # Any of them may exit on its own between the listing and the signal.
    for process in tree:
        with suppress(psutil.NoSuchProcess):
            process.terminate()
    _, still_running = psutil.wait_procs(tree, timeout=GRACE_SECONDS)
    for process in still_running:
        with suppress(psutil.NoSuchProcess):
            process.kill()
    psutil.wait_procs(still_running, timeout=GRACE_SECONDS)
